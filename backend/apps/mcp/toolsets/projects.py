from apps.mcp.errors import MCPToolError
from apps.mcp.services import projects_service
from apps.mcp.utils.common import to_int


def _require_found(data, label):
    if data is None:
        raise MCPToolError(f'{label}不存在')
    return data


def list_projects(arguments):
    return projects_service.list_projects(
        query=(arguments.get('query') or '').strip(),
        status=(arguments.get('status') or '').strip(),
        series_id=(arguments.get('series_id') or '').strip(),
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


def get_project_detail(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return _require_found(projects_service.get_project_detail(project_id), '项目')


def get_project_stages(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return _require_found(projects_service.get_project_stages(project_id), '项目')


def list_series(arguments):
    return projects_service.list_series(
        query=(arguments.get('query') or '').strip(),
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


def get_series_detail(arguments):
    series_id = (arguments.get('series_id') or '').strip()
    if not series_id:
        raise MCPToolError('缺少 series_id')
    return _require_found(projects_service.get_series_detail(series_id), '作品')


def get_project_statistics(arguments):
    return projects_service.get_project_statistics()


def run_project_pipeline(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return projects_service.run_project_pipeline(project_id)


def pause_project(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return projects_service.pause_project(project_id)


def resume_project(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return projects_service.resume_project(project_id)


def execute_project_stage(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    stage_name = (arguments.get('stage_name') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if not stage_name:
        raise MCPToolError('缺少 stage_name')
    return projects_service.execute_project_stage(project_id, stage_name, arguments.get('input_data') or {})


def get_project_task_status(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    task_id = (arguments.get('task_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if not task_id:
        raise MCPToolError('缺少 task_id')
    return projects_service.get_project_task_status(project_id, task_id)


TOOL_DEFINITIONS = [
    {
        'name': 'list_projects',
        'description': '列出项目，支持按关键词、状态和作品过滤。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'status': {'type': 'string'},
                'series_id': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_projects,
    },
    {
        'name': 'get_project_detail',
        'description': '查询单个项目详情，包括阶段、模型配置和资产绑定。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {'project_id': {'type': 'string'}},
        },
        'handler': get_project_detail,
    },
    {
        'name': 'get_project_stages',
        'description': '查询项目阶段详情和领域数据。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {'project_id': {'type': 'string'}},
        },
        'handler': get_project_stages,
    },
    {
        'name': 'list_series',
        'description': '列出作品。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_series,
    },
    {
        'name': 'get_series_detail',
        'description': '查询作品详情和分集列表。',
        'inputSchema': {
            'type': 'object',
            'required': ['series_id'],
            'properties': {'series_id': {'type': 'string'}},
        },
        'handler': get_series_detail,
    },
    {
        'name': 'get_project_statistics',
        'description': '查询项目状态统计概览。',
        'inputSchema': {'type': 'object', 'properties': {}},
        'handler': get_project_statistics,
    },
    {
        'name': 'run_project_pipeline',
        'description': '触发项目完整工作流。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {'project_id': {'type': 'string'}},
        },
        'handler': run_project_pipeline,
    },
    {
        'name': 'pause_project',
        'description': '暂停处理中的项目。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {'project_id': {'type': 'string'}},
        },
        'handler': pause_project,
    },
    {
        'name': 'resume_project',
        'description': '恢复已暂停项目。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {'project_id': {'type': 'string'}},
        },
        'handler': resume_project,
    },
    {
        'name': 'execute_project_stage',
        'description': '触发项目指定阶段执行。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'stage_name'],
            'properties': {
                'project_id': {'type': 'string'},
                'stage_name': {'type': 'string'},
                'input_data': {'type': 'object', 'default': {}},
            },
        },
        'handler': execute_project_stage,
    },
    {
        'name': 'get_project_task_status',
        'description': '查询项目异步任务状态。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'task_id'],
            'properties': {
                'project_id': {'type': 'string'},
                'task_id': {'type': 'string'},
            },
        },
        'handler': get_project_task_status,
    },
]
