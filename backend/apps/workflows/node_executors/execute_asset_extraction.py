"""资产抽取节点执行逻辑。"""

import time
import uuid
from typing import Any, Dict, List

import requests
from django.db.models import Q

from apps.ai_proxy.views import _build_provider_payload, _parse_float, _parse_int, _pick_provider
from apps.projects.utils import parse_json
from apps.prompts.models import GlobalVariable
from core.ai_client.factory import create_ai_client

from ..models import WorkflowNodeRun
from .llm_helpers import collect_llm_stream_text
from .response_helpers import extract_assistant_text
from .template_helpers import render_asset_extraction_system_prompt, resolve_asset_extraction_template


def _serialize_asset_candidate(asset: GlobalVariable) -> Dict[str, Any]:
    """将 GlobalVariable 序列化为候选资产数据。"""
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
    """归一化单条资产抽取结果，并匹配候选资产。"""
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


def execute_asset_extraction(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行资产抽取节点，调用 LLM 从文本中提取资产。"""
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

    prompt_template = resolve_asset_extraction_template(node_run, input_payload)
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

    system_prompt = render_asset_extraction_system_prompt(project, prompt_template, input_payload)
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
        stream_result = collect_llm_stream_text(
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
        generated_text = extract_assistant_text(result)

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
