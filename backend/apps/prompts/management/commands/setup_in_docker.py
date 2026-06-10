import logging
import multiprocessing
import os
import shutil
import sys
from pathlib import Path

from distutils.core import Extension, setup

from Cython.Build import cythonize
from django.core.management.base import BaseCommand, CommandError


NB_COMPILE_JOBS = multiprocessing.cpu_count()
LOGGER = logging.getLogger("encrypt-py")

FORMATTER = logging.Formatter("%(asctime)s|%(levelname)s| %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(FORMATTER)

if not LOGGER.handlers:
    LOGGER.addHandler(HANDLER)
LOGGER.setLevel(logging.DEBUG)

EXCLUDED_DIRS = {
    "__pycache__",
    "migrations",
    "tests",
}
EXCLUDED_FILES = {
    "__init__.py",
    "apps.py",
    "manage.py",
}
COMPILED_APPS = (
    "agent",
    "mcp",
    "workflows",
)


def walk_python_files(target_path):
    path = Path(target_path)
    if path.is_file() and path.suffix == ".py":
        yield str(path)
        return

    for current_path, dir_names, file_names in os.walk(path):
        dir_names[:] = [name for name in dir_names if name not in EXCLUDED_DIRS]
        for file_name in file_names:
            if not file_name.endswith(".py"):
                continue
            if file_name in EXCLUDED_FILES:
                continue
            yield str(Path(current_path) / file_name)


def delete_source_and_generated_c_files(py_files):
    for py_file in py_files:
        source_file = Path(py_file)
        c_file = Path(py_file).with_suffix(".c")
        if source_file.exists():
            source_file.unlink()
        if c_file.exists():
            c_file.unlink()


def delete_build_cache(path):
    target_path = Path(path)
    for current_path, dir_names, _ in os.walk(target_path):
        for dir_name in list(dir_names):
            if dir_name != "__pycache__":
                continue
            shutil.rmtree(Path(current_path) / dir_name, ignore_errors=True)


def delete_closed_source_test_dirs(path):
    target_path = Path(path)
    for current_path, dir_names, _ in os.walk(target_path):
        for dir_name in list(dir_names):
            if dir_name != "tests":
                continue
            shutil.rmtree(Path(current_path) / dir_name, ignore_errors=True)


def delete_python_bytecode(path):
    target_path = Path(path)
    for bytecode_file in list(target_path.rglob("*.pyc")) + list(target_path.rglob("*.pyo")):
        bytecode_file.unlink(missing_ok=True)


def rename_compiled_extensions(path):
    for extension in Path(path).rglob("*.so"):
        stem = extension.name[:-len(extension.suffix)]
        new_name = f"{stem.split('.', 1)[0]}{extension.suffix}"
        if new_name != extension.name:
            os.replace(str(extension), str(extension.with_name(new_name)))
    for extension in Path(path).rglob("*.pyd"):
        stem = extension.name[:-len(extension.suffix)]
        new_name = f"{stem.split('.', 1)[0]}{extension.suffix}"
        if new_name != extension.name:
            os.replace(str(extension), str(extension.with_name(new_name)))


def chunk_list(items, chunk_count):
    if not items:
        return []

    chunk_count = max(1, min(chunk_count, len(items)))
    size = len(items) // chunk_count
    remainder = len(items) % chunk_count
    result = []
    start = 0
    for index in range(chunk_count):
        end = start + size + (1 if index < remainder else 0)
        result.append(items[start:end])
        start = end
    return [chunk for chunk in result if chunk]


def module_name_from_path(py_file, base_dir):
    return Path(py_file).resolve().relative_to(base_dir).with_suffix("").as_posix().replace("/", ".")


def compile_python_files(py_files, build_path, base_dir):
    compiled_files = []
    failed_files = []
    total_count = len(py_files)

    for index, py_file in enumerate(py_files, start=1):
        file_name = os.path.basename(py_file)
        success = False

        for attempt in range(1, 4):
            try:
                LOGGER.debug("编译进行中 %s/%s, %s (try %s)", index, total_count, file_name, attempt)
                setup(
                    name="ai_story_closed_source_build",
                    packages=[],
                    ext_modules=cythonize(
                        [Extension(module_name_from_path(py_file, base_dir), [py_file])],
                        quiet=True,
                        language_level=3,
                    ),
                    script_args=["build_ext", "-t", str(build_path), "--inplace"],
                )
                compiled_files.append(py_file)
                LOGGER.debug("编译成功 %s", py_file)
                success = True
                break
            except Exception as exc:
                LOGGER.exception("编译失败 %s, 错误 %s (try %s)", py_file, exc, attempt)
                c_file = Path(py_file).with_suffix(".c")
                if c_file.exists():
                    c_file.unlink()

        if not success:
            LOGGER.error("编译最终失败，尝试了3次: %s", py_file)
            failed_files.append(py_file)

    return compiled_files, failed_files


def run_compile(args):
    file_list, build_path, base_dir = args
    return compile_python_files(file_list, build_path, base_dir)


class Command(BaseCommand):
    help = "在 docker 环境中编译闭源应用为 so/pyd 文件，并删除已编译的源码"

    def handle(self, *args, **options):
        if os.getenv("AI_STORY_COMPILE_CLOSED_SOURCE") != "1":
            raise CommandError("setup_in_docker 会删除源码，只能在设置 AI_STORY_COMPILE_CLOSED_SOURCE=1 后执行")

        base_dir = Path(__file__).resolve().parents[4]
        build_path = base_dir / "build"
        target_dirs = [base_dir / "apps" / app_name for app_name in COMPILED_APPS]

        os.chdir(base_dir)
        build_path.mkdir(parents=True, exist_ok=True)
        py_files = []
        for target_dir in target_dirs:
            if not target_dir.exists():
                LOGGER.warning("目标目录不存在，跳过: %s", target_dir)
                continue
            py_files.extend(walk_python_files(target_dir))

        py_files = sorted(set(py_files))

        if not py_files:
            LOGGER.warning("未找到可编译的 Python 文件，目标目录: %s", ", ".join(str(path) for path in target_dirs))
            return

        LOGGER.debug(">>> 开始编译，总共 %s 个进程，目标文件 %s 个", NB_COMPILE_JOBS, len(py_files))
        tasks = [(chunk, build_path, base_dir) for chunk in chunk_list(py_files, NB_COMPILE_JOBS)]

        if len(tasks) == 1:
            compiled_groups = [run_compile(tasks[0])]
        else:
            with multiprocessing.Pool(processes=len(tasks)) as pool:
                compiled_groups = pool.map(run_compile, tasks)

        compiled_files = [file_path for compiled, _ in compiled_groups for file_path in compiled]
        failed_files = [file_path for _, failed in compiled_groups for file_path in failed]

        for target_dir in target_dirs:
            rename_compiled_extensions(target_dir)
            delete_build_cache(target_dir)

        LOGGER.debug("删除 build 目录 %s", build_path)
        shutil.rmtree(build_path, ignore_errors=True)

        if failed_files:
            raise CommandError("部分文件编译失败，已停止删除源码: {}".format(", ".join(failed_files)))

        delete_source_and_generated_c_files(compiled_files)
        for target_dir in target_dirs:
            delete_closed_source_test_dirs(target_dir)
            delete_python_bytecode(target_dir)
        LOGGER.debug(">>> 编译完成，生成扩展文件 %s 个，已删除对应源码", len(compiled_files))
