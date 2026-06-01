"""改写节点执行逻辑。"""

import base64
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import requests
from django.conf import settings

from apps.ai_proxy.views import _build_provider_payload, _pick_provider

from .response_helpers import extract_assistant_text

DEFAULT_REWRITE_SYSTEM_PROMPT = (
    '你是专业的中文剧本编辑。请基于用户提供的原始内容和修改要求，'
    '给出清晰、可执行的修改建议或改写结果。'
)


def _ensure_url_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


def _guess_image_mime_type(image_url: str, content_type: str = '') -> str:
    normalized_type = (content_type or '').split(';', 1)[0].strip().lower()
    if normalized_type.startswith('image/'):
        return normalized_type

    guessed_type, _ = mimetypes.guess_type(image_url)
    if guessed_type and guessed_type.startswith('image/'):
        return guessed_type

    return 'image/png'


def _read_image_url_as_data_uri(image_url: str, timeout: int) -> str:
    if not image_url:
        return ''

    if image_url.startswith('data:image/') and ';base64,' in image_url:
        return image_url

    if image_url.startswith('/api/v1/content/storage/image/'):
        relative_path = image_url.split('/api/v1/content/storage/image/', 1)[1]
        image_path = Path(settings.STORAGE_ROOT) / 'image' / relative_path
        image_bytes = image_path.read_bytes()
        mime_type = _guess_image_mime_type(str(image_path))
        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f'data:{mime_type};base64,{encoded}'

    response = requests.get(image_url, timeout=timeout)
    response.raise_for_status()
    mime_type = _guess_image_mime_type(image_url, response.headers.get('Content-Type', ''))
    encoded = base64.b64encode(response.content).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'


def execute_rewrite(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行改写节点，调用 LLM 生成改写结果。"""
    model = input_payload.get('model', '')
    provider = _pick_provider('llm', model)
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    original_text = (input_payload.get('original_text') or '').strip()
    upstream_text = (input_payload.get('upstream_text') or '').strip()
    upstream_image_urls = _ensure_url_list(input_payload.get('upstream_image_urls'))
    upstream_video_urls = _ensure_url_list(input_payload.get('upstream_video_urls'))
    instruction = (input_payload.get('instruction') or '').strip()

    if not original_text:
        raise RuntimeError('缺少 original_text')
    if not instruction:
        raise RuntimeError('缺少 instruction')

    prompt_sections = []
    if upstream_text:
        prompt_sections.append(f'上游参考内容：\n{upstream_text}')
    if upstream_video_urls:
        prompt_sections.append(
            '上游视频参考链接：\n'
            + '\n'.join(upstream_video_urls)
            + '\n请结合这些视频内容进行参考。'
        )
    prompt_sections.append(
        f'原始内容：\n{original_text}\n\n'
        f'修改要求：\n{instruction}\n\n'
        '请基于原始内容输出修改建议或改写结果。'
    )
    prompt_text = '\n\n'.join(section for section in prompt_sections if section)

    if upstream_image_urls:
        encoded_image_urls = [
            _read_image_url_as_data_uri(image_url, int(provider.timeout or 60))
            for image_url in upstream_image_urls
        ]
        message_content = [
            {
                'type': 'text',
                'text': prompt_text,
            },
        ]
        for image_url in encoded_image_urls:
            message_content.append({
                'type': 'image_url',
                'image_url': {
                    'url': image_url,
                },
            })
        messages = [
            {'role': 'system', 'content': DEFAULT_REWRITE_SYSTEM_PROMPT},
            {'role': 'user', 'content': message_content},
        ]
    else:
        messages = [
            {'role': 'system', 'content': DEFAULT_REWRITE_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt_text},
        ]

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
        'upstream_image_urls': upstream_image_urls,
        'upstream_video_urls': upstream_video_urls,
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
