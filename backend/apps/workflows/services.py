"""工作流回填服务。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from django.db import transaction
from django.utils import timezone

from apps.content.models import CameraMovement, ContentRewrite, GeneratedImage, GeneratedVideo, Storyboard
from apps.projects.models import Project, ProjectStage
from apps.projects.utils import ensure_project_stages
from apps.workflows.models import WorkflowBinding, WorkflowEdge, WorkflowNode, WorkflowNodeRun


def _payload_dict(node_run: WorkflowNodeRun) -> Dict[str, Any]:
    payload = node_run.normalized_output or node_run.output_payload or {}
    return payload if isinstance(payload, dict) else {}


def _storyboard_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get('storyboards')
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def can_auto_apply_workflow_node_result(node_run: WorkflowNodeRun) -> bool:
    """判断当前节点结果是否满足 ai_story 领域回填的最小结构。"""
    payload = _payload_dict(node_run)
    node_type = node_run.node_type

    if node_type == 'rewrite':
        return bool(payload.get('rewritten_text'))

    if node_type in {'storyboard', 'camera_movement', 'image_generation', 'video_generation'}:
        return bool(_storyboard_items(payload))

    return False


def get_downstream_node_ids(canvas, source_node_ids: Iterable[str | int]) -> List[str]:
    """获取指定节点集合的所有下游节点。"""
    pending = {str(node_id) for node_id in source_node_ids if node_id}
    visited: Set[str] = set()
    downstream_ids: List[str] = []

    while pending:
        batch = list(pending)
        pending.clear()
        edges = WorkflowEdge.objects.filter(
            canvas=canvas,
            is_enabled=True,
            source_node_id__in=batch,
        ).values_list('target_node_id', flat=True)
        for target_id in edges:
            target_id_str = str(target_id)
            if target_id_str in visited or target_id_str in {str(node_id) for node_id in source_node_ids if node_id}:
                continue
            visited.add(target_id_str)
            downstream_ids.append(target_id_str)
            pending.add(target_id_str)

    return downstream_ids


def mark_nodes_status(node_ids: Iterable[str | int], status: str) -> None:
    node_ids = [str(node_id) for node_id in node_ids if node_id]
    if not node_ids:
        return
    WorkflowNode.objects.filter(id__in=node_ids).exclude(status='running').update(
        status=status,
        updated_at=timezone.now(),
    )


def mark_downstream_nodes_stale(canvas, source_node_ids: Iterable[str | int], include_sources: bool = False) -> List[str]:
    """将下游节点标记为 stale；未执行过的节点标记为 dirty。"""
    downstream_ids = get_downstream_node_ids(canvas, source_node_ids)
    if include_sources:
        downstream_ids = [*{*downstream_ids, *[str(node_id) for node_id in source_node_ids if node_id]}]

    if not downstream_ids:
        return []

    queryset = WorkflowNode.objects.filter(id__in=downstream_ids).exclude(status='running')
    stale_ids = list(queryset.filter(status__in=['completed', 'failed', 'stale']).values_list('id', flat=True))
    dirty_ids = list(queryset.exclude(status__in=['completed', 'failed', 'stale', 'running']).values_list('id', flat=True))

    if stale_ids:
        WorkflowNode.objects.filter(id__in=stale_ids).update(status='stale', updated_at=timezone.now())
    if dirty_ids:
        WorkflowNode.objects.filter(id__in=dirty_ids).update(status='dirty', updated_at=timezone.now())
    return [str(node_id) for node_id in downstream_ids]


def _ensure_stage(project: Project, stage_name: str) -> ProjectStage:
    ensure_project_stages(project=project, stage_types=[stage_name])
    return ProjectStage.objects.get(project=project, stage_type=stage_name)


def _mark_stage(project: Project, stage_name: str, *, status_value: str = 'completed', output_data: Optional[dict] = None) -> None:
    ensure_project_stages(project=project, stage_types=[stage_name])
    defaults = {
        'status': status_value,
        'started_at': timezone.now(),
        'completed_at': timezone.now() if status_value in ('completed', 'skipped') else None,
        'error_message': '',
    }
    if output_data is not None:
        defaults['output_data'] = output_data
    ProjectStage.objects.filter(project=project, stage_type=stage_name).update(**defaults)


def _resolve_storyboard(project_id, item: Dict[str, Any]) -> Storyboard:
    storyboard_id = item.get('storyboard_id') or item.get('id')
    if storyboard_id:
        return Storyboard.objects.get(id=storyboard_id, project_id=project_id)

    sequence_number = item.get('sequence_number')
    if sequence_number in (None, ''):
        raise ValueError('缺少 storyboard_id 或 sequence_number')
    return Storyboard.objects.get(project_id=project_id, sequence_number=sequence_number)


def _resolve_or_create_storyboard_binding(node_run: WorkflowNodeRun, storyboard: Storyboard) -> None:
    WorkflowBinding.objects.update_or_create(
        workflow_run=node_run.workflow_run,
        canvas=node_run.canvas,
        node=node_run.node,
        node_run=node_run,
        binding_type='storyboard',
        target_key=f'storyboard:{storyboard.sequence_number}',
        defaults={
            'target_id': str(storyboard.id),
            'sequence_number': storyboard.sequence_number,
            'metadata': {},
        },
    )


def _upsert_generated_image(
    *,
    node_run: WorkflowNodeRun,
    storyboard: Storyboard,
    image_payload: Dict[str, Any],
    index: int,
) -> GeneratedImage:
    target_key = str(
        image_payload.get('external_task_id')
        or image_payload.get('id')
        or image_payload.get('image_url')
        or f'{storyboard.sequence_number}:{index}'
    )
    binding = WorkflowBinding.objects.filter(
        workflow_run=node_run.workflow_run,
        canvas=node_run.canvas,
        node=node_run.node,
        node_run=node_run,
        binding_type='image',
        target_key=target_key,
    ).first()

    defaults = {
        'storyboard': storyboard,
        'image_url': image_payload.get('image_url') or image_payload.get('url') or '',
        'thumbnail_url': image_payload.get('thumbnail_url') or '',
        'generation_params': {
            **(image_payload.get('generation_params') or {}),
            'external_task_id': image_payload.get('external_task_id') or node_run.external_task_id,
            'source_node_run_id': str(node_run.id),
        },
        'status': image_payload.get('status') or 'completed',
        'width': image_payload.get('width') or 0,
        'height': image_payload.get('height') or 0,
        'file_size': image_payload.get('file_size') or 0,
    }
    if not defaults['image_url']:
        raise ValueError('图片回填缺少 image_url')

    if binding:
        image = GeneratedImage.objects.get(id=binding.target_id)
        for field, value in defaults.items():
            setattr(image, field, value)
        image.save()
    else:
        image = GeneratedImage.objects.create(**defaults)
        WorkflowBinding.objects.create(
            workflow_run=node_run.workflow_run,
            canvas=node_run.canvas,
            node=node_run.node,
            node_run=node_run,
            binding_type='image',
            target_id=str(image.id),
            target_key=target_key,
            sequence_number=storyboard.sequence_number,
            metadata={},
        )
    return image


def _resolve_image_for_video(node_run: WorkflowNodeRun, storyboard: Storyboard, video_payload: Dict[str, Any]) -> GeneratedImage:
    image_id = video_payload.get('image_id')
    if image_id:
        return GeneratedImage.objects.get(id=image_id, storyboard=storyboard)
    image = GeneratedImage.objects.filter(storyboard=storyboard).order_by('-created_at').first()
    if not image:
        raise ValueError(f'分镜 {storyboard.sequence_number} 缺少可关联图片')
    return image


def _resolve_camera_for_video(node_run: WorkflowNodeRun, storyboard: Storyboard, video_payload: Dict[str, Any]) -> CameraMovement:
    camera_id = video_payload.get('camera_movement_id')
    if camera_id:
        return CameraMovement.objects.get(id=camera_id, storyboard=storyboard)
    camera = CameraMovement.objects.filter(storyboard=storyboard).first()
    if not camera:
        raise ValueError(f'分镜 {storyboard.sequence_number} 缺少可关联运镜')
    return camera


def _upsert_generated_video(
    *,
    node_run: WorkflowNodeRun,
    storyboard: Storyboard,
    video_payload: Dict[str, Any],
    index: int,
) -> GeneratedVideo:
    target_key = str(
        video_payload.get('external_task_id')
        or video_payload.get('id')
        or video_payload.get('video_url')
        or f'{storyboard.sequence_number}:{index}'
    )
    binding = WorkflowBinding.objects.filter(
        workflow_run=node_run.workflow_run,
        canvas=node_run.canvas,
        node=node_run.node,
        node_run=node_run,
        binding_type='video',
        target_key=target_key,
    ).first()
    image = _resolve_image_for_video(node_run, storyboard, video_payload)
    camera = _resolve_camera_for_video(node_run, storyboard, video_payload)

    defaults = {
        'storyboard': storyboard,
        'image': image,
        'camera_movement': camera,
        'video_url': video_payload.get('video_url') or video_payload.get('url') or '',
        'thumbnail_url': video_payload.get('thumbnail_url') or '',
        'duration': video_payload.get('duration') or 0,
        'width': video_payload.get('width') or 0,
        'height': video_payload.get('height') or 0,
        'fps': video_payload.get('fps') or 24,
        'file_size': video_payload.get('file_size') or 0,
        'generation_params': {
            **(video_payload.get('generation_params') or {}),
            'external_task_id': video_payload.get('external_task_id') or node_run.external_task_id,
            'source_node_run_id': str(node_run.id),
        },
        'status': video_payload.get('status') or 'completed',
    }
    if not defaults['video_url']:
        raise ValueError('视频回填缺少 video_url')

    if binding:
        video = GeneratedVideo.objects.get(id=binding.target_id)
        for field, value in defaults.items():
            setattr(video, field, value)
        video.save()
    else:
        video = GeneratedVideo.objects.create(**defaults)
        WorkflowBinding.objects.create(
            workflow_run=node_run.workflow_run,
            canvas=node_run.canvas,
            node=node_run.node,
            node_run=node_run,
            binding_type='video',
            target_id=str(video.id),
            target_key=target_key,
            sequence_number=storyboard.sequence_number,
            metadata={},
        )
    return video


@transaction.atomic
def apply_workflow_node_result(node_run: WorkflowNodeRun) -> Dict[str, Any]:
    """将节点标准化输出回填到 ai_story 领域模型。"""

    project = None
    if node_run.canvas and node_run.canvas.project_id:
        project = node_run.canvas.project
    elif node_run.workflow_run and node_run.workflow_run.project_id:
        project = node_run.workflow_run.project
    if not project:
        raise ValueError('当前节点运行未绑定 project，无法回填')

    payload = _payload_dict(node_run)
    node_type = node_run.node_type

    if node_type == 'rewrite':
        rewritten_text = payload.get('rewritten_text')
        if rewritten_text in (None, ''):
            raise ValueError('rewrite 节点缺少 rewritten_text')
        rewrite, _ = ContentRewrite.objects.update_or_create(
            project=project,
            defaults={
                'original_text': payload.get('original_text') or project.original_topic,
                'rewritten_text': rewritten_text,
                'generation_metadata': payload.get('generation_metadata') or {},
            },
        )
        _mark_stage(project, 'rewrite', output_data=payload)
        WorkflowBinding.objects.update_or_create(
            workflow_run=node_run.workflow_run,
            canvas=node_run.canvas,
            node=node_run.node,
            node_run=node_run,
            binding_type='stage',
            target_key='rewrite',
            defaults={'target_id': str(rewrite.id), 'metadata': {}},
        )
        return {'node_type': node_type, 'rewrite_id': str(rewrite.id)}

    if node_type == 'storyboard':
        storyboards = _storyboard_items(payload)
        if not storyboards:
            raise ValueError('storyboard 节点缺少 storyboards')
        results = []
        for item in storyboards:
            sequence_number = item.get('sequence_number')
            if sequence_number in (None, ''):
                raise ValueError('分镜回填缺少 sequence_number')
            storyboard, _ = Storyboard.objects.update_or_create(
                project=project,
                sequence_number=sequence_number,
                defaults={
                    'scene_description': item.get('scene_description') or '',
                    'narration_text': item.get('narration_text') or '',
                    'image_prompt': item.get('image_prompt') or '',
                    'duration_seconds': item.get('duration_seconds') or 3.0,
                    'generation_metadata': item.get('generation_metadata') or {},
                },
            )
            _resolve_or_create_storyboard_binding(node_run, storyboard)
            results.append({'storyboard_id': str(storyboard.id), 'sequence_number': storyboard.sequence_number})
        _mark_stage(project, 'storyboard', output_data=payload)
        return {'node_type': node_type, 'storyboards': results}

    if node_type == 'camera_movement':
        storyboards = _storyboard_items(payload)
        if not storyboards:
            raise ValueError('camera_movement 节点缺少 storyboards')
        results = []
        for item in storyboards:
            storyboard = _resolve_storyboard(project.id, item)
            camera_payload = item.get('camera_movement') or item
            camera, _ = CameraMovement.objects.update_or_create(
                storyboard=storyboard,
                defaults={
                    'movement_type': camera_payload.get('movement_type') or '',
                    'movement_params': camera_payload.get('movement_params') or {},
                    'generation_metadata': camera_payload.get('generation_metadata') or {},
                },
            )
            WorkflowBinding.objects.update_or_create(
                workflow_run=node_run.workflow_run,
                canvas=node_run.canvas,
                node=node_run.node,
                node_run=node_run,
                binding_type='camera',
                target_key=f'camera:{storyboard.sequence_number}',
                defaults={
                    'target_id': str(camera.id),
                    'sequence_number': storyboard.sequence_number,
                    'metadata': {},
                },
            )
            results.append({'camera_id': str(camera.id), 'storyboard_id': str(storyboard.id)})
        _mark_stage(project, 'camera_movement', output_data=payload)
        return {'node_type': node_type, 'cameras': results}

    if node_type == 'image_generation':
        storyboards = _storyboard_items(payload)
        if not storyboards:
            raise ValueError('image_generation 节点缺少 storyboards')
        results = []
        for item in storyboards:
            storyboard = _resolve_storyboard(project.id, item)
            images = item.get('images') or []
            if not isinstance(images, list) or not images:
                continue
            for index, image_payload in enumerate(images, start=1):
                image = _upsert_generated_image(
                    node_run=node_run,
                    storyboard=storyboard,
                    image_payload=image_payload,
                    index=index,
                )
                results.append({'image_id': str(image.id), 'storyboard_id': str(storyboard.id)})
        _mark_stage(project, 'image_generation', output_data=payload)
        return {'node_type': node_type, 'images': results}

    if node_type == 'video_generation':
        storyboards = _storyboard_items(payload)
        if not storyboards:
            raise ValueError('video_generation 节点缺少 storyboards')
        results = []
        for item in storyboards:
            storyboard = _resolve_storyboard(project.id, item)
            videos = item.get('videos') or []
            if not isinstance(videos, list) or not videos:
                continue
            for index, video_payload in enumerate(videos, start=1):
                video = _upsert_generated_video(
                    node_run=node_run,
                    storyboard=storyboard,
                    video_payload=video_payload,
                    index=index,
                )
                results.append({'video_id': str(video.id), 'storyboard_id': str(storyboard.id)})
        _mark_stage(project, 'video_generation', output_data=payload)
        return {'node_type': node_type, 'videos': results}

    raise ValueError(f'暂不支持节点类型 {node_type} 的回填')


def handle_node_run_completed(node_run: WorkflowNodeRun, *, latest_output: Optional[dict] = None) -> None:
    """节点执行完成后，更新节点状态并传播下游失效。"""
    node = node_run.node
    if not node:
        return

    updates = {
        'status': 'completed',
        'last_executed_at': timezone.now(),
        'updated_at': timezone.now(),
    }
    if latest_output is not None:
        updates['latest_output'] = latest_output
    WorkflowNode.objects.filter(id=node.id).update(**updates)
    mark_downstream_nodes_stale(node.canvas, [node.id])
