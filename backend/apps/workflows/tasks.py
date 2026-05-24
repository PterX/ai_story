"""工作流节点异步任务。"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
from celery import shared_task
from core.ai_client.base import AIResponse
from core.ai_client.factory import create_ai_client
from core.ai_client.image_service import ImageGenerationService
from core.ai_client.schemas import ImageEditRequest, Text2ImageRequest
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from jinja2 import Template, TemplateError

from apps.ai_proxy.views import (
    _build_provider_payload,
    _ensure_list,
    _parse_float,
    _parse_int,
    _parse_size,
    _pick_provider,
)
from apps.projects.asset_context import build_project_asset_context
from apps.projects.utils import parse_json, parse_storyboard_json
from apps.prompts.models import GlobalVariable, PromptTemplate, PromptTemplateSet

from .models import WorkflowNode, WorkflowNodeRun
from .services import (
    apply_workflow_node_result,
    can_auto_apply_workflow_node_result,
    handle_node_run_completed,
)

logger = logging.getLogger(__name__)

DEFAULT_REWRITE_SYSTEM_PROMPT = (
    '你是专业的中文剧本编辑。请基于用户提供的原始内容和修改要求，'
    '给出清晰、可执行的修改建议或改写结果。'
)

MULTIPLIER_TOKEN_MAP = {
    '1x': 1000,
    '2x': 2000,
    '3x': 3000,
    '4x': 4000,
    '5x': 5000,
}


def _extract_assistant_text(response: Dict[str, Any]) -> str:
    content = (((response or {}).get('choices') or [{}])[0].get('message') or {}).get('content')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get('type') == 'text':
                parts.append(item.get('text') or '')
        return '\n'.join(part for part in parts if part).strip()
    return ''


def _extract_image_url(response: Dict[str, Any]) -> str:
    first_item = (response.get('data') or [None])[0] if isinstance(response.get('data'), list) else response.get('data')
    if isinstance(first_item, str):
        return first_item
    if isinstance(first_item, dict):
        if first_item.get('url'):
            return first_item['url']
        if first_item.get('image_url'):
            return first_item['image_url']
        if first_item.get('b64_json'):
            return f"data:image/png;base64,{first_item['b64_json']}"
    if isinstance(response.get('url'), str):
        return response['url']
    return ''


def _extract_video_url(response: Dict[str, Any]) -> str:
    first_item = (response.get('data') or [None])[0] if isinstance(response.get('data'), list) else response.get('data')
    if isinstance(first_item, str):
        return first_item
    if isinstance(first_item, dict):
        if first_item.get('url'):
            return first_item['url']
        if first_item.get('video_url'):
            return first_item['video_url']
    if isinstance(response.get('url'), str):
        return response['url']
    return ''


def _get_default_storyboard_template() -> Optional[PromptTemplate]:
    template_set = PromptTemplateSet.objects.filter(is_default=True).first()
    if not template_set:
        return None
    return (
        PromptTemplate.objects
        .select_related('model_provider', 'template_set')
        .filter(template_set=template_set, stage_type='storyboard', is_active=True)
        .first()
    )


def _resolve_storyboard_template(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Optional[PromptTemplate]:
    template_id = input_payload.get('prompt_template_id') or input_payload.get('promptTemplateId')
    queryset = PromptTemplate.objects.select_related('model_provider', 'template_set').filter(
        stage_type='storyboard',
        is_active=True,
    )

    if template_id:
        template = queryset.filter(id=template_id).first()
        if template:
            return template

    project = getattr(node_run.canvas, 'project', None)
    template_set = getattr(project, 'prompt_template_set', None) if project else None
    if template_set:
        template = queryset.filter(template_set=template_set).first()
        if template:
            return template

    return _get_default_storyboard_template()


def _get_default_asset_extraction_template() -> Optional[PromptTemplate]:
    template_set = PromptTemplateSet.objects.filter(is_default=True).first()
    if not template_set:
        return None
    return (
        PromptTemplate.objects
        .select_related('model_provider', 'template_set')
        .filter(template_set=template_set, stage_type='asset_extraction', is_active=True)
        .first()
    )


def _resolve_asset_extraction_template(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Optional[PromptTemplate]:
    template_id = input_payload.get('prompt_template_id') or input_payload.get('promptTemplateId')
    queryset = PromptTemplate.objects.select_related('model_provider', 'template_set').filter(
        stage_type='asset_extraction',
        is_active=True,
    )

    if template_id:
        template = queryset.filter(id=template_id).first()
        if template:
            return template

    project = getattr(node_run.canvas, 'project', None)
    template_set = getattr(project, 'prompt_template_set', None) if project else None
    if template_set:
        template = queryset.filter(template_set=template_set).first()
        if template:
            return template

    return _get_default_asset_extraction_template()


def _build_storyboard_template_vars(project, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    global_vars = build_project_asset_context(project)

    return {
        **global_vars,
        'project': {
            'name': project.name,
            'description': project.description,
            'original_topic': project.original_topic,
        },
        'raw_text': raw_text,
        'original_text': raw_text,
        'text': raw_text,
        'human_text': input_payload.get('human_text') or '',
        'instruction': input_payload.get('instruction') or '',
    }


def _build_asset_extraction_template_vars(project, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('source_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    global_vars = build_project_asset_context(project)

    return {
        **global_vars,
        'project': {
            'name': project.name,
            'description': project.description,
            'original_topic': project.original_topic,
        },
        'raw_text': raw_text,
        'source_text': raw_text,
        'original_text': raw_text,
        'text': raw_text,
        'human_text': input_payload.get('human_text') or '',
    }


def _render_storyboard_system_prompt(project, template: PromptTemplate, input_payload: Dict[str, Any]) -> str:
    try:
        return Template(template.template_content).render(**_build_storyboard_template_vars(project, input_payload))
    except TemplateError as exc:
        raise RuntimeError(f'分镜提示词模板渲染失败: {exc}') from exc


def _render_asset_extraction_system_prompt(project, template: PromptTemplate, input_payload: Dict[str, Any]) -> str:
    try:
        return Template(template.template_content).render(**_build_asset_extraction_template_vars(project, input_payload))
    except TemplateError as exc:
        raise RuntimeError(f'资产抽取提示词模板渲染失败: {exc}') from exc


def _serialize_asset_candidate(asset: GlobalVariable) -> Dict[str, Any]:
    image_url = ''
    if getattr(asset, 'image_file', None):
        try:
            image_url = asset.image_file.url
        except Exception:
            image_url = ''

    return {
        'asset_id': str(asset.id),
        'key': asset.key,
        'group': asset.group,
        'description': asset.description,
        'variable_type': asset.variable_type,
        'scope': asset.scope,
        'scope_display': asset.get_scope_display(),
        'image_url': image_url,
    }


def _normalize_asset_item(project, item: Dict[str, Any], index: int) -> Dict[str, Any]:
    raw_key = item.get('key') or item.get('label') or f'asset_{index}'
    key = str(raw_key or '').strip() or f'asset_{index}'
    label = str(item.get('label') or key).strip() or key
    group = str(item.get('group') or '未分组').strip() or '未分组'
    variable_type = item.get('variable_type') or 'image'
    if variable_type not in {'string', 'number', 'boolean', 'json', 'image'}:
        variable_type = 'image'

    value = item.get('value')
    if value is None:
        value = item.get('content')
    if value is None:
        value = item.get('data')
    if value is None:
        value = ''

    if variable_type == 'json' and isinstance(value, str):
        value = {'text': value}

    query = GlobalVariable.objects.filter(is_active=True).filter(
        Q(created_by=project.user, scope='user') | Q(scope='system')
    )
    candidates = list(query.filter(key=key).order_by('scope', 'group', 'key')[:3])
    if len(candidates) < 3 and key:
        existing_ids = {asset.id for asset in candidates}
        fuzzy = query.filter(key__icontains=key).order_by('scope', 'group', 'key')[:6]
        for asset in fuzzy:
            if asset.id not in existing_ids:
                candidates.append(asset)
                existing_ids.add(asset.id)
            if len(candidates) >= 3:
                break

    serialized_candidates = [_serialize_asset_candidate(asset) for asset in candidates[:3]]
    return {
        'temp_id': f'item_{index}',
        'key': key,
        'label': label,
        'group': group,
        'variable_type': variable_type,
        'value': value,
        'confidence': max(0.0, min(1.0, _parse_float(item.get('confidence'), 0.0) or 0.0)),
        'match_status': 'matched' if serialized_candidates else 'unmatched',
        'candidates': serialized_candidates,
        'selected_asset_id': serialized_candidates[0]['asset_id'] if len(serialized_candidates) == 1 else None,
        'selected_action': None,
    }


def _normalize_storyboard_scene(scene: Dict[str, Any], fallback_index: int) -> Dict[str, Any]:
    sequence_number = _parse_int(scene.get('scene_number'), fallback_index) or fallback_index
    narration_text = (scene.get('narration') or '').strip()
    image_prompt = (scene.get('visual_prompt') or '').strip()
    shot_type = (scene.get('shot_type') or '').strip()

    return {
        'sequence_number': sequence_number,
        'scene_description': shot_type,
        'narration_text': narration_text,
        'image_prompt': image_prompt,
        'duration_seconds': _parse_float(scene.get('duration'), 3.0) or 3.0,
        'generation_metadata': {
            'shot_type': shot_type,
            'raw_scene_data': scene,
        },
    }


def _collect_llm_stream_text(
    client,
    *,
    user_prompt: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float = 1.0,
) -> Dict[str, Any]:
    full_text = ''
    response_metadata: Dict[str, Any] = {}
    start_time = time.time()
    stream = client.generate_stream(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    for chunk in stream:
        chunk_type = chunk.get('type')
        if chunk_type == 'token':
            full_text = chunk.get('full_text', full_text + chunk.get('content', ''))
            continue
        if chunk_type == 'done':
            full_text = chunk.get('full_text', full_text)
            response_metadata = chunk.get('metadata') or {}
            break
        if chunk_type == 'error':
            raise RuntimeError(chunk.get('error') or '分镜流式生成失败')

    latency_ms = response_metadata.get('latency_ms') or int((time.time() - start_time) * 1000)
    return {
        'text': full_text,
        'latency_ms': latency_ms,
        'metadata': response_metadata,
    }


def _build_image_context(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    size = _parse_size(input_payload.get('size'))
    width = _parse_int(input_payload.get('width'), size['width'])
    height = _parse_int(input_payload.get('height'), size['height'])
    reference_images = _ensure_list(
        input_payload.get('image') or input_payload.get('images') or input_payload.get('source_images')
    )
    source_image_url = input_payload.get('source_image_url')
    if source_image_url and source_image_url not in reference_images:
        reference_images.insert(0, source_image_url)

    return {
        'model': input_payload.get('model', ''),
        'prompt': input_payload.get('prompt', ''),
        'negative_prompt': input_payload.get('negative_prompt', ''),
        'mask': input_payload.get('mask') or input_payload.get('mask_image') or '',
        'width': width,
        'height': height,
        'reference_images': reference_images,
        'aspect_ratio': input_payload.get('aspect_ratio') or input_payload.get('ratio') or '',
        'sample_count': _parse_int(input_payload.get('n'), _parse_int(input_payload.get('sample_count'), 1)) or 1,
        'seed': _parse_int(input_payload.get('seed')),
        'strength': _parse_float(input_payload.get('strength'), 0.35) or 0.35,
        'mode': input_payload.get('mode') or input_payload.get('edit_mode') or '',
        'provider_type': input_payload.get('provider_type') or '',
        'force_edit': input_payload.get('force_edit') is True,
        'extra': {
            key: value for key, value in input_payload.items()
            if key not in {
                'model', 'prompt', 'negative_prompt', 'mask', 'mask_image', 'width', 'height',
                'image', 'images', 'source_images', 'source_image_url', 'aspect_ratio', 'ratio',
                'n', 'sample_count', 'seed', 'strength', 'mode', 'edit_mode', 'size',
                'provider_type', 'force_edit',
            }
        },
    }


def _resolve_image_provider_type(context: Dict[str, Any]) -> str:
    mode = str(context.get('mode') or '').lower()
    reference_images = context.get('reference_images') or []
    if mode in {'inpaint', 'img2img', 'image_edit', 'edit'}:
        return 'image_edit'
    if context.get('mask'):
        return 'image_edit'
    if context.get('provider_type') == 'image_edit':
        return 'image_edit'
    if reference_images and context.get('force_edit'):
        return 'image_edit'
    return 'text2image'


def _normalize_image_response(result: AIResponse, provider, provider_type: str) -> Dict[str, Any]:
    if not result.success:
        raise RuntimeError(result.error or '图片生成失败')
    return {
        'id': f'imggen-{uuid.uuid4().hex[:8]}',
        'object': 'list',
        'created': int(time.time()),
        'model': provider.model_name,
        'provider': _build_provider_payload(provider),
        'provider_type': provider_type,
        'data': result.data if isinstance(result.data, list) else _ensure_list(result.data),
        'text': result.text,
        'metadata': result.metadata,
    }


def _normalize_video_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, AIResponse):
        return {
            'success': result.success,
            'data': result.data if isinstance(result.data, list) else _ensure_list(result.data),
            'metadata': result.metadata,
            'error': result.error,
        }
    if isinstance(result, dict):
        normalized_data = result.get('data', [])
        if not isinstance(normalized_data, list):
            normalized_data = _ensure_list(normalized_data)
        return {
            'success': result.get('success', True),
            'data': normalized_data,
            'metadata': result.get('metadata', {}),
            'error': result.get('error'),
        }
    return {
        'success': False,
        'data': [],
        'metadata': {},
        'error': '无法识别的视频响应格式',
    }


def _mark_run_running(node_run_id: str, task_id: str = '') -> WorkflowNodeRun:
    with transaction.atomic():
        node_run = WorkflowNodeRun.objects.select_related('node').get(id=node_run_id)
        node_run.status = 'running'
        node_run.error_message = ''
        node_run.started_at = node_run.started_at or timezone.now()
        update_fields = ['status', 'error_message', 'started_at', 'updated_at']
        if task_id and node_run.external_task_id != task_id:
            node_run.external_task_id = task_id
            update_fields.append('external_task_id')
        node_run.save(update_fields=update_fields)
        if node_run.node_id:
            WorkflowNode.objects.filter(id=node_run.node_id).update(
                status='running',
                updated_at=timezone.now(),
            )
        return node_run


def _finalize_success(
    node_run_id: str,
    *,
    output_payload: Dict[str, Any],
    normalized_output: Dict[str, Any],
) -> None:
    with transaction.atomic():
        node_run = WorkflowNodeRun.objects.select_related('node', 'canvas', 'workflow_run').get(id=node_run_id)
        node_run.status = 'completed'
        node_run.output_payload = output_payload
        node_run.normalized_output = normalized_output
        node_run.error_message = ''
        node_run.completed_at = timezone.now()
        node_run.save(
            update_fields=['status', 'output_payload', 'normalized_output', 'error_message', 'completed_at', 'updated_at']
        )
        handle_node_run_completed(node_run, latest_output=normalized_output)
        if can_auto_apply_workflow_node_result(node_run):
            apply_workflow_node_result(node_run)


def _finalize_failure(node_run_id: str, error_message: str) -> None:
    error_text = (error_message or '节点执行失败').strip()
    with transaction.atomic():
        node_run = WorkflowNodeRun.objects.select_related('node').get(id=node_run_id)
        node_run.status = 'failed'
        node_run.error_message = error_text
        node_run.completed_at = timezone.now()
        node_run.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
        if node_run.node_id:
            WorkflowNode.objects.filter(id=node_run.node_id).update(
                status='failed',
                updated_at=timezone.now(),
            )


def _execute_rewrite(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    model = input_payload.get('model', '')
    provider = _pick_provider('llm', model)
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    original_text = (input_payload.get('original_text') or '').strip()
    instruction = (input_payload.get('instruction') or '').strip()
    multiplier = input_payload.get('multiplier') or '2x'

    if not original_text:
        raise RuntimeError('缺少 original_text')
    if not instruction:
        raise RuntimeError('缺少 instruction')

    payload = {
        'model': provider.model_name,
        'messages': [
            {'role': 'system', 'content': DEFAULT_REWRITE_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': (
                    f'原始内容：\n{original_text}\n\n'
                    f'修改要求：\n{instruction}\n\n'
                    '请基于原始内容输出修改建议或改写结果。'
                ),
            },
        ],
        'temperature': input_payload.get('temperature', 0.7),
        'max_tokens': MULTIPLIER_TOKEN_MAP.get(multiplier, MULTIPLIER_TOKEN_MAP['2x']),
        'stream': False,
    }
    headers = {
        'Authorization': f'Bearer {provider.api_key}',
        'Content-Type': 'application/json',
    }
    start_time = time.time()
    response = requests.post(
        provider.api_url,
        headers=headers,
        json=payload,
        timeout=provider.timeout,
    )
    latency_ms = int((time.time() - start_time) * 1000)
    if response.status_code != 200:
        raise RuntimeError(f'上游 API 请求失败: {response.status_code}')
    result = response.json()
    if 'id' not in result:
        result['id'] = f'chatcmpl-{uuid.uuid4().hex[:8]}'
    result.setdefault('model', provider.model_name)
    result.setdefault('metadata', {})
    result['metadata'].update({
        'latency_ms': latency_ms,
        'provider': _build_provider_payload(provider),
    })
    assistant_text = _extract_assistant_text(result) or '模型未返回可显示的修改建议'
    normalized_output = {
        'text': assistant_text,
        'rewritten_text': assistant_text,
        'original_text': original_text,
        'instruction': instruction,
        'prompt': instruction,
        'model': model or provider.model_name,
        'multiplier': multiplier,
        'generation_metadata': {
            'source': 'linknow',
        },
    }
    return {
        'output_payload': result,
        'normalized_output': normalized_output,
    }


def _execute_storyboard(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    project = getattr(node_run.canvas, 'project', None)
    if not project:
        raise RuntimeError('当前工作流画板未绑定项目，无法生成分镜')

    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    if not raw_text:
        raise RuntimeError('缺少分镜生成所需的文本内容')

    prompt_template = _resolve_storyboard_template(node_run, input_payload)
    if not prompt_template:
        raise RuntimeError('未找到可用的分镜提示词模板')

    resolved_model = (input_payload.get('model') or '').strip()
    provider = _pick_provider('llm', resolved_model or (prompt_template.model_provider.model_name if prompt_template.model_provider else ''))
    if not provider and prompt_template.model_provider:
        provider = prompt_template.model_provider
    if not provider:
        provider = _pick_provider('llm', '')
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    system_prompt = _render_storyboard_system_prompt(project, prompt_template, input_payload)
    user_prompt = f'## 用户输入\n{raw_text}'
    max_tokens = _parse_int(input_payload.get('max_tokens'), 40960) or 40960
    temperature = input_payload.get('temperature', 0.8)
    top_p = input_payload.get('top_p', 1.0)

    client = create_ai_client(provider)
    # 分镜输出较长，给流式读取更宽的超时窗口，避免长文本响应中途被 requests 读超时打断。
    client.config['timeout'] = max(int(client.config.get('timeout') or 0), int(provider.timeout or 0), 300)

    result = {
        'id': f'chatcmpl-{uuid.uuid4().hex[:8]}',
        'model': provider.model_name,
        'metadata': {},
    }

    if hasattr(client, 'generate_stream'):
        stream_result = _collect_llm_stream_text(
            client,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        generated_text = stream_result['text']
        result['metadata'].update(stream_result.get('metadata') or {})
        result['metadata']['latency_ms'] = stream_result['latency_ms']
    else:
        payload = {
            'model': provider.model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False,
        }
        headers = {
            'Authorization': f'Bearer {provider.api_key}',
            'Content-Type': 'application/json',
        }

        start_time = time.time()
        response = requests.post(
            provider.api_url,
            headers=headers,
            json=payload,
            timeout=max(int(provider.timeout or 0), 300),
        )
        latency_ms = int((time.time() - start_time) * 1000)
        if response.status_code != 200:
            raise RuntimeError(f'上游 API 请求失败: {response.status_code}')

        result = response.json()
        if 'id' not in result:
            result['id'] = f'chatcmpl-{uuid.uuid4().hex[:8]}'
        result.setdefault('model', provider.model_name)
        result.setdefault('metadata', {})
        result['metadata']['latency_ms'] = latency_ms
        generated_text = _extract_assistant_text(result)

    result.setdefault('metadata', {})
    result['metadata'].update({
        'provider': _build_provider_payload(provider),
        'prompt_template_id': str(prompt_template.id),
        'prompt_template_name': prompt_template.template_set.name,
    })

    if not generated_text:
        raise RuntimeError('模型未返回可解析的分镜内容')

    parsed_storyboard = parse_storyboard_json(generated_text)
    scenes = parsed_storyboard.get('scenes', [])
    storyboards = [
        _normalize_storyboard_scene(scene, index)
        for index, scene in enumerate(scenes, start=1)
    ]
    if not storyboards:
        raise RuntimeError('分镜结果为空')

    normalized_output = {
        'text': generated_text,
        'raw_text': raw_text,
        'model': resolved_model or provider.model_name,
        'prompt_template_id': str(prompt_template.id),
        'prompt_template_name': prompt_template.template_set.name,
        'storyboards': storyboards,
    }
    return {
        'output_payload': {
            **result,
            'parsed_storyboard': parsed_storyboard,
        },
        'normalized_output': normalized_output,
    }


def _execute_asset_extraction(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    project = getattr(node_run.canvas, 'project', None)
    if not project:
        raise RuntimeError('当前工作流画板未绑定项目，无法执行资产抽取')

    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('source_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    if not raw_text:
        raise RuntimeError('缺少资产抽取所需的文本内容')

    prompt_template = _resolve_asset_extraction_template(node_run, input_payload)
    if not prompt_template:
        raise RuntimeError('未找到可用的资产抽取提示词模板')

    resolved_model = (input_payload.get('model') or '').strip()
    provider = _pick_provider('llm', resolved_model or (prompt_template.model_provider.model_name if prompt_template.model_provider else ''))
    if not provider and prompt_template.model_provider:
        provider = prompt_template.model_provider
    if not provider:
        provider = _pick_provider('llm', '')
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    system_prompt = _render_asset_extraction_system_prompt(project, prompt_template, input_payload)
    user_prompt = f'## 用户输入\n{raw_text}'
    max_tokens = _parse_int(input_payload.get('max_tokens'), 4096) or 4096
    temperature = input_payload.get('temperature', 0.3)
    top_p = input_payload.get('top_p', 1.0)

    client = create_ai_client(provider)
    client.config['timeout'] = max(int(client.config.get('timeout') or 0), int(provider.timeout or 0), 180)

    result = {
        'id': f'chatcmpl-{uuid.uuid4().hex[:8]}',
        'model': provider.model_name,
        'metadata': {},
    }

    if hasattr(client, 'generate_stream'):
        stream_result = _collect_llm_stream_text(
            client,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        generated_text = stream_result['text']
        result['metadata'].update(stream_result.get('metadata') or {})
        result['metadata']['latency_ms'] = stream_result['latency_ms']
    else:
        payload = {
            'model': provider.model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False,
        }
        headers = {
            'Authorization': f'Bearer {provider.api_key}',
            'Content-Type': 'application/json',
        }

        start_time = time.time()
        response = requests.post(
            provider.api_url,
            headers=headers,
            json=payload,
            timeout=max(int(provider.timeout or 0), 180),
        )
        latency_ms = int((time.time() - start_time) * 1000)
        if response.status_code != 200:
            raise RuntimeError(f'上游 API 请求失败: {response.status_code}')

        result = response.json()
        if 'id' not in result:
            result['id'] = f'chatcmpl-{uuid.uuid4().hex[:8]}'
        result.setdefault('model', provider.model_name)
        result.setdefault('metadata', {})
        result['metadata']['latency_ms'] = latency_ms
        generated_text = _extract_assistant_text(result)

    result.setdefault('metadata', {})
    result['metadata'].update({
        'provider': _build_provider_payload(provider),
        'prompt_template_id': str(prompt_template.id),
        'prompt_template_name': prompt_template.template_set.name,
    })

    if not generated_text:
        raise RuntimeError('模型未返回可解析的资产抽取内容')

    parsed_output = parse_json(generated_text)
    if not isinstance(parsed_output, dict):
        parsed_output = {}
    raw_items = parsed_output.get('assets') or parsed_output.get('items') or []
    if not isinstance(raw_items, list):
        raw_items = []
    items = [
        _normalize_asset_item(project, item, index)
        for index, item in enumerate(raw_items, start=1)
        if isinstance(item, dict)
    ]

    normalized_output = {
        'text': generated_text,
        'raw_text': raw_text,
        'source_text': raw_text,
        'source_type': input_payload.get('source_type') or 'manual',
        'summary': str(parsed_output.get('summary') or parsed_output.get('description') or '').strip(),
        'model': resolved_model or provider.model_name,
        'prompt_template_id': str(prompt_template.id),
        'prompt_template_name': prompt_template.template_set.name,
        'items': items,
    }
    return {
        'output_payload': {
            **result,
            'parsed_output': parsed_output,
        },
        'normalized_output': normalized_output,
    }


def _execute_image_generation(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    context = _build_image_context(input_payload)
    if not context['prompt']:
        raise RuntimeError('prompt 不能为空')

    provider_type = _resolve_image_provider_type(context)
    provider = _pick_provider(provider_type, context['model'])
    if not provider:
        raise RuntimeError(f'没有可用的 {provider_type} 模型提供商')

    client = create_ai_client(provider)
    if provider_type == 'image_edit':
        ai_response = ImageGenerationService.edit(
            provider,
            ImageEditRequest(
                source_images=context['reference_images'],
                prompt=context['prompt'],
                mask_image=context['mask'],
                negative_prompt=context['negative_prompt'],
                strength=context['strength'],
                width=context['width'],
                height=context['height'],
                edit_mode=context['mode'] or 'img2img',
                extra=context['extra'],
            ),
            client=client,
        )
    else:
        ai_response = ImageGenerationService.generate(
            provider,
            Text2ImageRequest(
                prompt=context['prompt'],
                negative_prompt=context['negative_prompt'],
                reference_images=context['reference_images'],
                width=context['width'],
                height=context['height'],
                aspect_ratio=context['aspect_ratio'],
                sample_count=context['sample_count'],
                seed=context['seed'],
                extra=context['extra'],
            ),
            client=client,
        )

    output_payload = _normalize_image_response(ai_response, provider, provider_type)
    image_url = _extract_image_url(output_payload)
    if not image_url:
        raise RuntimeError('模型未返回可用图片地址')

    normalized_output = {
        'imageUrl': image_url,
        'image_url': image_url,
        'prompt': context['prompt'],
        'model': context['model'] or provider.model_name,
        'scale': input_payload.get('scale') or '1x',
        'source_image_url': (context['reference_images'] or [''])[0] if context['reference_images'] else '',
        'text': input_payload.get('text') or '',
    }
    return {
        'output_payload': output_payload,
        'normalized_output': normalized_output,
    }


def _execute_video_generation(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = input_payload.get('prompt', '')
    model = input_payload.get('model', '')
    image_inputs = _ensure_list(input_payload.get('image_urls') or input_payload.get('images') or input_payload.get('source_images'))
    image_input = input_payload.get('image_url') or input_payload.get('image')
    if image_input and image_input not in image_inputs:
        image_inputs.insert(0, image_input)
    image_base64 = input_payload.get('image_base64')
    image_base64s = _ensure_list(input_payload.get('image_base64s'))

    if not prompt:
        raise RuntimeError('prompt 不能为空')
    if not image_inputs and not image_base64 and not image_base64s:
        raise RuntimeError('缺少可用于生成视频的图片输入')

    provider = _pick_provider('image2video', model)
    if not provider:
        raise RuntimeError('没有可用的视频模型提供商')

    client = create_ai_client(provider)
    raw_result = client._generate_video(
        prompt=prompt,
        model=provider.model_name,
        image_uri=image_inputs[0] if image_inputs else '',
        image_uris=image_inputs,
        image_base64=image_base64,
        image_base64s=image_base64s,
        image_mime_type=input_payload.get('image_mime_type', 'image/jpeg'),
        duration_seconds=_parse_int(input_payload.get('duration_seconds'), _parse_int(input_payload.get('duration'), 5)) or 5,
        sample_count=_parse_int(input_payload.get('sample_count'), _parse_int(input_payload.get('n'), 1)) or 1,
        aspect_ratio=input_payload.get('aspect_ratio') or input_payload.get('ratio') or '16:9',
        resolution=input_payload.get('resolution'),
        seed=_parse_int(input_payload.get('seed')),
        negative_prompt=input_payload.get('negative_prompt'),
        generate_audio=input_payload.get('generate_audio', True),
        camera_movement_description=(
            input_payload.get('camera_movement_description')
            or input_payload.get('cameraMovementDescription')
            or ''
        ),
    )
    result = _normalize_video_result(raw_result)
    if not result['success']:
        raise RuntimeError(result['error'] or '视频生成失败')

    output_payload = {
        'id': f'vidgen-{uuid.uuid4().hex[:8]}',
        'object': 'list',
        'created': int(time.time()),
        'model': provider.model_name,
        'provider': _build_provider_payload(provider),
        'data': result['data'],
        'metadata': result['metadata'],
    }
    video_url = _extract_video_url(output_payload)
    if not video_url:
        raise RuntimeError('模型未返回可用视频地址')

    normalized_output = {
        'videoUrl': video_url,
        'video_url': video_url,
        'prompt': prompt,
        'model': model or provider.model_name,
        'duration': input_payload.get('duration') or '5s',
        'aspectRatio': input_payload.get('aspect_ratio') or input_payload.get('aspectRatio') or '16:9',
        'resolution': input_payload.get('resolution') or '720p',
        'image_urls': image_inputs,
        'text': input_payload.get('text') or '',
    }
    return {
        'output_payload': output_payload,
        'normalized_output': normalized_output,
    }


def _dispatch_node_execution(node_run: WorkflowNodeRun) -> Dict[str, Any]:
    input_payload = node_run.input_payload or {}
    if node_run.node_type == 'rewrite':
        return _execute_rewrite(input_payload)
    if node_run.node_type == 'asset_extraction':
        return _execute_asset_extraction(node_run, input_payload)
    if node_run.node_type == 'storyboard':
        return _execute_storyboard(node_run, input_payload)
    if node_run.node_type == 'image_generation':
        return _execute_image_generation(input_payload)
    if node_run.node_type == 'video_generation':
        return _execute_video_generation(input_payload)
    raise RuntimeError(f'暂不支持节点类型 {node_run.node_type} 的异步执行')


@shared_task(bind=True, autoretry_for=(), retry_backoff=False, retry_kwargs=None)
def execute_workflow_node_task(self, node_run_id: str) -> Dict[str, Any]:
    """异步执行单个工作流节点。"""
    node_run = _mark_run_running(node_run_id, self.request.id or '')
    try:
        result = _dispatch_node_execution(node_run)
        _finalize_success(
            node_run_id,
            output_payload=result['output_payload'],
            normalized_output=result['normalized_output'],
        )
        return {
            'success': True,
            'node_run_id': node_run_id,
            'task_id': self.request.id,
        }
    except Exception as exc:
        logger.exception('工作流节点执行失败: node_run_id=%s node_type=%s', node_run_id, node_run.node_type)
        _finalize_failure(node_run_id, str(exc))
        raise
