"""Dynamic node-schema execution logic."""

import time
import uuid
from typing import Any, Dict

import requests

from apps.ai_proxy.views import _build_provider_payload, _parse_int, _pick_provider
from apps.projects.utils import parse_json
from apps.models.token_utils import create_ai_client_for_user

from ..models import WorkflowNodeRun
from ..node_schema_runtime import render_schema_system_prompt, resolve_node_schema
from .llm_helpers import collect_llm_stream_text
from .response_helpers import extract_assistant_text


DEFAULT_DYNAMIC_SCHEMA_SYSTEM_PROMPT = (
    '你是一个结构化内容生成助手。请严格按照节点结构定义要求输出 JSON，'
    '不要输出 Markdown 代码块以外的解释。'
)


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get_path(data: Any, path: str, default: Any = None) -> Any:
    if not path:
        return data
    current = data
    for part in str(path).split('.'):
        if isinstance(current, dict):
            current = current.get(part, default)
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else default
            continue
        return default
    return current


def execute_dynamic_schema(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a generic node backed by WorkflowNodeSchema."""
    schema = resolve_node_schema(node_run)
    if not schema:
        raise RuntimeError('动态结构节点缺少可用的节点结构定义')

    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('source_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    if not raw_text:
        raise RuntimeError('动态结构节点缺少输入文本')

    resolved_model = (input_payload.get('model') or '').strip()
    provider = _pick_provider('llm', resolved_model)
    if not provider:
        provider = _pick_provider('llm', '')
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    schema_config = _as_dict(schema.schema_config)
    output_schema = _as_dict(schema_config.get('output_schema'))
    max_tokens = _parse_int(input_payload.get('max_tokens'), 4096) or 4096
    temperature = input_payload.get('temperature', 0.4)
    top_p = input_payload.get('top_p', 1.0)
    system_prompt = render_schema_system_prompt(
        input_payload,
        schema.system_prompt or DEFAULT_DYNAMIC_SCHEMA_SYSTEM_PROMPT,
    )
    user_prompt = '\n'.join([
        f'## 节点结构\n{schema.name} ({schema.key})',
        f'## 输出要求\n输出类型: {output_schema.get("output_type") or "single"}',
        f'items_path: {output_schema.get("items_path") or ""}',
        f'source_text_path: {output_schema.get("source_text_path") or ""}',
        f'summary_path: {output_schema.get("summary_path") or ""}',
        f'## 用户输入\n{raw_text}',
    ]).strip()

    client = create_ai_client_for_user(provider, user=getattr(getattr(node_run.canvas, 'project', None), 'user', None))
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
            'Authorization': f'Bearer {client.api_key}',
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
        result.setdefault('id', f'chatcmpl-{uuid.uuid4().hex[:8]}')
        result.setdefault('model', provider.model_name)
        result.setdefault('metadata', {})
        result['metadata']['latency_ms'] = latency_ms
        generated_text = extract_assistant_text(result)

    if not generated_text:
        raise RuntimeError('模型未返回可解析的动态结构内容')

    parsed_output = parse_json(generated_text)
    if not isinstance(parsed_output, dict):
        parsed_output = {}

    items_path = str(output_schema.get('items_path') or 'items').strip()
    source_text_path = str(output_schema.get('source_text_path') or 'source_text').strip()
    summary_path = str(output_schema.get('summary_path') or 'summary').strip()
    items = _get_path(parsed_output, items_path, []) if items_path else []
    if not isinstance(items, list):
        items = []

    result.setdefault('metadata', {})
    result['metadata'].update({
        'provider': _build_provider_payload(provider),
        'node_schema_key': schema.key,
        'node_schema_name': schema.name,
    })

    normalized_output = {
        'text': generated_text,
        'raw_text': raw_text,
        'source_text': _get_path(parsed_output, source_text_path, raw_text) if source_text_path else raw_text,
        'summary': _get_path(parsed_output, summary_path, '') if summary_path else '',
        'model': resolved_model or provider.model_name,
        'node_schema_key': schema.key,
        'node_schema_name': schema.name,
        'parsed_output': parsed_output,
        'items': items,
    }
    return {
        'output_payload': {
            **result,
            'parsed_output': parsed_output,
        },
        'normalized_output': normalized_output,
    }
