"""改写节点执行逻辑。"""

import time
import uuid
from typing import Any, Dict

import requests

from apps.ai_proxy.views import _build_provider_payload, _pick_provider

from .response_helpers import extract_assistant_text

DEFAULT_REWRITE_SYSTEM_PROMPT = (
    '你是专业的中文剧本编辑。请基于用户提供的原始内容和修改要求，'
    '给出清晰、可执行的修改建议或改写结果。'
)


def execute_rewrite(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行改写节点，调用 LLM 生成改写结果。"""
    model = input_payload.get('model', '')
    provider = _pick_provider('llm', model)
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    original_text = (input_payload.get('original_text') or '').strip()
    upstream_text = (input_payload.get('upstream_text') or '').strip()
    instruction = (input_payload.get('instruction') or '').strip()

    if not original_text:
        raise RuntimeError('缺少 original_text')
    if not instruction:
        raise RuntimeError('缺少 instruction')

    messages = [
        {'role': 'system', 'content': DEFAULT_REWRITE_SYSTEM_PROMPT},
    ]
    if upstream_text:
        messages.append({
            'role': 'user',
            'content': f'上游参考内容：\n{upstream_text}',
        })
    messages.append({
        'role': 'user',
        'content': (
            f'原始内容：\n{original_text}\n\n'
            f'修改要求：\n{instruction}\n\n'
            '请基于原始内容输出修改建议或改写结果。'
        ),
    })

    payload = {
        'model': provider.model_name,
        'messages': messages,
        'temperature': input_payload.get('temperature', 0.7),
        'max_tokens': provider.max_tokens,
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
    assistant_text = extract_assistant_text(result) or '模型未返回可显示的修改建议'
    normalized_output = {
        'text': assistant_text,
        'rewritten_text': assistant_text,
        'original_text': original_text,
        'upstream_text': upstream_text,
        'instruction': instruction,
        'prompt': instruction,
        'model': model or provider.model_name,
        'generation_metadata': {
            'source': 'linknow',
        },
    }
    return {
        'output_payload': result,
        'normalized_output': normalized_output,
    }
