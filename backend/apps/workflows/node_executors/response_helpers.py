"""响应数据提取与归一化工具函数。"""

import time
import uuid
from typing import Any, Dict, List, Optional

from core.ai_client.base import AIResponse

from apps.ai_proxy.views import _build_provider_payload, _ensure_list


def extract_assistant_text(response: Dict[str, Any]) -> str:
    """从 LLM 聊天响应中提取 assistant 文本。"""
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


def extract_image_url(response: Dict[str, Any]) -> str:
    """从图片生成响应中提取图片 URL。"""
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


def extract_video_url(response: Dict[str, Any]) -> str:
    """从视频生成响应中提取视频 URL。"""
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


def normalize_image_response(result: AIResponse, provider, provider_type: str) -> Dict[str, Any]:
    """将图片生成的 AIResponse 归一化为统一输出格式。"""
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


def normalize_video_result(result: Any) -> Dict[str, Any]:
    """将视频生成的原始结果归一化为统一输出格式。"""
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
