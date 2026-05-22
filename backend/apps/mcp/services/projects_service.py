from celery.result import AsyncResult
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.projects.models import Project, Series
from apps.projects.serializers import (
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectStageSerializer,
    SeriesDetailSerializer,
    SeriesListSerializer,
)
from apps.projects.utils import is_stage_template_enabled


def list_projects(*, query='', status='', series_id='', limit=20):
    queryset = (
        Project.objects.all()
        .select_related('user', 'prompt_template_set', 'series')
        .prefetch_related('stages', 'queue_tasks')
        .order_by('-created_at')
    )
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(original_topic__icontains=query)
            | Q(episode_title__icontains=query)
        )
    if status:
        queryset = queryset.filter(status=status)
    if series_id:
        queryset = queryset.filter(series_id=series_id)

    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': ProjectListSerializer(items, many=True).data,
    }


def get_project_detail(project_id):
    project = (
        Project.objects.filter(id=project_id)
        .select_related('user', 'prompt_template_set', 'series', 'model_config')
        .prefetch_related(
            'stages',
            'queue_tasks',
            'asset_bindings__asset',
            'model_config__rewrite_providers',
            'model_config__storyboard_providers',
            'model_config__image_providers',
            'model_config__camera_providers',
            'model_config__video_providers',
        )
        .first()
    )
    if not project:
        return None
    return ProjectDetailSerializer(project).data


def get_project_stages(project_id):
    project = Project.objects.filter(id=project_id).first()
    if not project:
        return None
    stages = project.stages.all().order_by('created_at')
    return {
        'project_id': str(project.id),
        'count': stages.count(),
        'results': ProjectStageSerializer(stages, many=True).data,
    }


def list_series(*, query='', limit=20):
    queryset = Series.objects.all().prefetch_related('episodes__stages').select_related('user').order_by('-created_at')
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': SeriesListSerializer(items, many=True).data,
    }


def get_series_detail(series_id):
    series = (
        Series.objects.filter(id=series_id)
        .select_related('user')
        .prefetch_related('episodes__stages', 'episodes__queue_tasks', 'episodes__prompt_template_set')
        .first()
    )
    if not series:
        return None
    return SeriesDetailSerializer(series).data


def get_project_statistics():
    projects = Project.objects.all()
    return {
        'total_projects': projects.count(),
        'draft_projects': projects.filter(status='draft').count(),
        'processing_projects': projects.filter(status='processing').count(),
        'completed_projects': projects.filter(status='completed').count(),
        'failed_projects': projects.filter(status='failed').count(),
        'paused_projects': projects.filter(status='paused').count(),
    }


def _project_task_cache_key(project_id):
    return 'project_active_tasks:{project_id}'.format(project_id=project_id)


def _register_project_task(project_id, task_id):
    task_ids = cache.get(_project_task_cache_key(project_id), [])
    if task_id not in task_ids:
        task_ids.append(task_id)
    cache.set(_project_task_cache_key(project_id), task_ids, timeout=24 * 60 * 60)


def _get_project_task_ids(project_id):
    return cache.get(_project_task_cache_key(project_id), [])


def _clear_project_tasks(project_id):
    cache.delete(_project_task_cache_key(project_id))


def _revoke_project_tasks(project_id):
    revoked_task_ids = []
    for task_id in _get_project_task_ids(project_id):
        try:
            AsyncResult(task_id).revoke(terminate=True)
            revoked_task_ids.append(task_id)
        except Exception:
            continue
    _clear_project_tasks(project_id)
    return revoked_task_ids


def _serialize_async_task(task_id, channel, project_id, extra=None):
    payload = {
        'task_id': task_id,
        'channel': channel,
        'project_id': str(project_id),
    }
    if extra:
        payload.update(extra)
    return payload


def run_project_pipeline(project_id):
    from apps.projects.queue_service import enqueue_episode_task
    from apps.projects.tasks import run_full_pipeline_task

    project = get_object_or_404(Project, id=project_id)

    if not project.series_id:
        if project.status != 'processing':
            project.status = 'processing'
            project.completed_at = None
            project.save(update_fields=['status', 'completed_at', 'updated_at'])

        task = run_full_pipeline_task.delay(project_id=str(project.id), user_id=project.user_id)
        _register_project_task(str(project.id), task.id)
        return _serialize_async_task(
            task.id,
            'ai_story:project:{project_id}:pipeline'.format(project_id=project.id),
            project.id,
            {'message': '工作流已启动'},
        )

    queue_result = enqueue_episode_task(project=project, created_by=project.user, task_type='pipeline')
    queue_task = queue_result['queue_task']
    if queue_result['started']:
        message = '工作流已启动'
    elif queue_result['already_exists']:
        message = '该分集已有待执行任务'
    else:
        message = '当前有分集正在执行，已进入等待队列'

    return {
        'task_id': queue_task.celery_task_id or None,
        'queue_task_id': str(queue_task.id),
        'queue_status': queue_task.status,
        'queue_position': queue_result['queue_position'],
        'channel': 'ai_story:project:{project_id}:pipeline'.format(project_id=project.id),
        'message': message,
        'project_id': str(project.id),
    }


def pause_project(project_id):
    from apps.projects.queue_service import cancel_running_queue_task

    project = get_object_or_404(Project, id=project_id)
    if project.status != 'processing':
        raise ValueError('只有处理中的项目才能暂停')

    revoked_task_ids = _revoke_project_tasks(str(project.id))
    project.stages.filter(status='processing').update(status='pending', completed_at=None, error_message='')
    cancel_running_queue_task(project)

    project.status = 'paused'
    project.save(update_fields=['status', 'updated_at'])

    return {
        'message': '项目已暂停',
        'project': ProjectDetailSerializer(project).data,
        'revoked_task_ids': revoked_task_ids,
    }


def resume_project(project_id):
    from apps.projects.queue_service import enqueue_episode_task

    project = get_object_or_404(Project, id=project_id)
    if project.status != 'paused':
        raise ValueError('只有暂停的项目才能恢复')

    if not project.series_id:
        return run_project_pipeline(project.id)

    queue_result = enqueue_episode_task(project=project, created_by=project.user, task_type='pipeline')
    queue_task = queue_result['queue_task']
    return {
        'message': '项目已恢复并重新加入队列' if not queue_result['started'] else '项目已恢复',
        'project': ProjectDetailSerializer(project).data,
        'task_id': queue_task.celery_task_id or None,
        'queue_task_id': str(queue_task.id),
        'queue_status': queue_task.status,
        'queue_position': queue_result['queue_position'],
        'channel': 'ai_story:project:{project_id}:pipeline'.format(project_id=project.id),
        'project_id': str(project.id),
    }


def execute_project_stage(project_id, stage_name, input_data=None):
    from apps.projects.tasks import (
        execute_image2video_stage,
        execute_image_edit_stage,
        execute_llm_stage,
        execute_multi_grid_image_stage,
        execute_text2image_stage,
    )

    input_data = input_data or {}
    project = get_object_or_404(Project, id=project_id)
    stage = get_object_or_404(project.stages, stage_type=stage_name)

    if not is_stage_template_enabled(project, stage_name):
        now = timezone.now()
        stage.status = 'skipped'
        stage.started_at = now
        stage.completed_at = now
        stage.error_message = '{label} 对应提示词模板未开启，已跳过该阶段'.format(label=stage.get_stage_type_display())
        stage.save(update_fields=['status', 'started_at', 'completed_at', 'error_message'])
        return {
            'message': stage.error_message,
            'skipped': True,
            'stage': ProjectStageSerializer(stage).data,
            'project_id': str(project.id),
        }

    if 'original_topic' in input_data and 'raw_text' not in input_data:
        input_data['raw_text'] = input_data['original_topic']

    if stage_name in ['rewrite', 'asset_extraction', 'storyboard', 'camera_movement']:
        task = execute_llm_stage.delay(
            project_id=str(project.id),
            stage_name=stage_name,
            input_data=input_data,
            user_id=project.user_id,
        )
    elif stage_name == 'image_generation':
        task = execute_text2image_stage.delay(
            project_id=str(project.id),
            storyboard_ids=input_data.get('storyboard_ids'),
            force_regenerate=input_data.get('force_regenerate', False),
            user_id=project.user_id,
        )
    elif stage_name == 'multi_grid_image':
        task = execute_multi_grid_image_stage.delay(
            project_id=str(project.id),
            storyboard_ids=input_data.get('storyboard_ids'),
            force_regenerate=input_data.get('force_regenerate', False),
            user_id=project.user_id,
            grid_rows=input_data.get('grid_rows', 2),
            grid_cols=input_data.get('grid_cols', 2),
            tile_gap=input_data.get('tile_gap', 0),
            outer_padding=input_data.get('outer_padding', 0),
        )
    elif stage_name == 'image_edit':
        task = execute_image_edit_stage.delay(
            project_id=str(project.id),
            storyboard_ids=input_data.get('storyboard_ids'),
            force_regenerate=input_data.get('force_regenerate', False),
            user_id=project.user_id,
            strength=input_data.get('strength', 0.35),
            width=input_data.get('width'),
            height=input_data.get('height'),
        )
    elif stage_name == 'video_generation':
        task = execute_image2video_stage.delay(
            project_id=str(project.id),
            storyboard_ids=input_data.get('storyboard_ids'),
            force_regenerate=input_data.get('force_regenerate', False),
            user_id=project.user_id,
        )
    else:
        raise ValueError('未知阶段类型: {stage_name}'.format(stage_name=stage_name))

    _register_project_task(str(project.id), task.id)
    return _serialize_async_task(
        task.id,
        'ai_story:project:{project_id}:stage:{stage_name}'.format(project_id=project.id, stage_name=stage_name),
        project.id,
        {
            'stage': stage_name,
            'message': '阶段 {stage_name} 任务已启动'.format(stage_name=stage_name),
        },
    )


def get_project_task_status(project_id, task_id):
    project = get_object_or_404(Project, id=project_id)
    task_result = AsyncResult(task_id)
    response_data = {
        'task_id': task_id,
        'state': task_result.state,
        'project_id': str(project.id),
    }
    if task_result.state == 'PENDING':
        response_data['info'] = '任务等待执行'
    elif task_result.state == 'STARTED':
        response_data['info'] = '任务正在执行'
    elif task_result.state == 'SUCCESS':
        response_data['result'] = task_result.result
        response_data['info'] = '任务执行成功'
    elif task_result.state == 'FAILURE':
        response_data['error'] = str(task_result.info)
        response_data['info'] = '任务执行失败'
    elif task_result.state == 'RETRY':
        response_data['info'] = '任务正在重试'
    else:
        response_data['info'] = task_result.info
    return response_data
