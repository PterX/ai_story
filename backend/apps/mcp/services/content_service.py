from django.shortcuts import get_object_or_404

from apps.content.models import (
    CameraMovement,
    ContentRewrite,
    Storyboard,
)
from apps.projects.models import Project


def _get_project(project_id):
    return get_object_or_404(Project, id=project_id)


def _serialize_rewrite(rewrite):
    return {
        'id': str(rewrite.id),
        'original_text': rewrite.original_text,
        'rewritten_text': rewrite.rewritten_text,
        'updated_at': rewrite.updated_at.isoformat() if rewrite.updated_at else None,
    }


def _serialize_storyboard(sb):
    data = {
        'id': str(sb.id),
        'sequence_number': sb.sequence_number,
        'scene_description': sb.scene_description,
        'narration_text': sb.narration_text,
        'image_prompt': sb.image_prompt,
        'duration_seconds': sb.duration_seconds,
        'updated_at': sb.updated_at.isoformat() if sb.updated_at else None,
    }
    camera = getattr(sb, 'camera_movement', None)
    if camera:
        data['camera_movement'] = {
            'id': str(camera.id),
            'movement_type': camera.movement_type,
            'movement_params': camera.movement_params,
        }
    images = list(sb.images.filter(status='completed').values(
        'id', 'image_url', 'thumbnail_url', 'status', 'width', 'height',
    ))
    for img in images:
        img['id'] = str(img['id'])
    data['images'] = images
    return data


def _serialize_camera_movement(camera):
    return {
        'id': str(camera.id),
        'storyboard_id': str(camera.storyboard_id),
        'movement_type': camera.movement_type,
        'movement_params': camera.movement_params,
        'updated_at': camera.updated_at.isoformat() if camera.updated_at else None,
    }


# ── 文案改写 ──────────────────────────────────────────────

def get_rewrite_content(project_id):
    project = _get_project(project_id)
    rewrite = ContentRewrite.objects.filter(project=project).first()
    if not rewrite:
        return None
    return _serialize_rewrite(rewrite)


def update_rewrite_content(project_id, rewritten_text, original_text=None):
    project = _get_project(project_id)
    defaults = {
        'rewritten_text': rewritten_text,
    }
    if original_text is not None:
        defaults['original_text'] = original_text
    elif not ContentRewrite.objects.filter(project=project).exists():
        defaults['original_text'] = project.original_topic or ''

    rewrite, _ = ContentRewrite.objects.update_or_create(
        project=project,
        defaults=defaults,
    )
    return {
        'message': '文案改写已更新',
        'rewrite': _serialize_rewrite(rewrite),
    }


# ── 分镜 ──────────────────────────────────────────────────

def list_storyboards(project_id):
    project = _get_project(project_id)
    storyboards = Storyboard.objects.filter(project=project).select_related(
        'camera_movement',
    ).prefetch_related('images')
    return {
        'project_id': str(project.id),
        'count': storyboards.count(),
        'results': [_serialize_storyboard(sb) for sb in storyboards],
    }


def get_storyboard_detail(project_id, storyboard_id):
    project = _get_project(project_id)
    storyboard = get_object_or_404(
        Storyboard.objects.select_related('camera_movement').prefetch_related('images'),
        id=storyboard_id,
        project=project,
    )
    return _serialize_storyboard(storyboard)


def update_storyboard(project_id, storyboard_id, **fields):
    project = _get_project(project_id)
    storyboard = get_object_or_404(Storyboard, id=storyboard_id, project=project)

    allowed = {'scene_description', 'narration_text', 'image_prompt', 'duration_seconds'}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if not updates:
        return {'message': '未提供可更新的字段', 'storyboard': _serialize_storyboard(storyboard)}

    for field, value in updates.items():
        setattr(storyboard, field, value)
    storyboard.save()

    return {
        'message': '分镜已更新',
        'storyboard': _serialize_storyboard(storyboard),
    }


# ── 运镜 ──────────────────────────────────────────────────

def get_camera_movement(project_id, camera_id):
    project = _get_project(project_id)
    camera = get_object_or_404(
        CameraMovement.objects.select_related('storyboard'),
        id=camera_id,
        storyboard__project=project,
    )
    return _serialize_camera_movement(camera)


def update_camera_movement(project_id, camera_id, **fields):
    project = _get_project(project_id)
    camera = get_object_or_404(
        CameraMovement,
        id=camera_id,
        storyboard__project=project,
    )

    allowed = {'movement_type', 'movement_params'}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    if not updates:
        return {'message': '未提供可更新的字段', 'camera_movement': _serialize_camera_movement(camera)}

    for field, value in updates.items():
        setattr(camera, field, value)
    camera.save()

    return {
        'message': '运镜参数已更新',
        'camera_movement': _serialize_camera_movement(camera),
    }
