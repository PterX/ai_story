"""图片协议执行器共享的结果处理工具。"""

from __future__ import annotations

import base64
import re
import uuid
from typing import Any, Iterable, List
from urllib.parse import urlparse

import requests

from core.utils.file_storage import image_storage


IMAGE_MARKDOWN_PATTERN = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
DATA_IMAGE_PATTERN = re.compile(r'data:image/[^;\s)]+;base64,[A-Za-z0-9+/=\s]+')
URL_PATTERN = re.compile(r'https?://\S+')


def build_storage_url(relative_path: str) -> str:
    return f'/api/v1/content/storage/image/{relative_path}'


def get_image_extension(content_type: str = '', source_url: str = '', content: bytes = b'') -> str:
    """根据响应头、URL 或二进制内容推断图片扩展名。"""
    type_map = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp',
        'image/svg+xml': '.svg',
    }
    normalized_type = (content_type or '').split(';', 1)[0].strip().lower()
    if normalized_type in type_map:
        return type_map[normalized_type]

    path = urlparse(source_url).path.lower()
    for extension in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'):
        if path.endswith(extension):
            return '.jpg' if extension == '.jpeg' else extension

    if content.startswith(b'\xFF\xD8\xFF'):
        return '.jpg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if content.startswith((b'GIF87a', b'GIF89a')):
        return '.gif'
    if content.startswith(b'RIFF') and b'WEBP' in content[:16]:
        return '.webp'
    if content.startswith(b'BM'):
        return '.bmp'
    if content.lstrip().startswith(b'<svg'):
        return '.svg'

    return '.png'


def download_image_to_storage(image_url: str, timeout: int) -> dict:
    if image_url.startswith('/api/v1/content/storage/image/'):
        relative_path = image_url.split('/api/v1/content/storage/image/', 1)[1]
        return {
            'url': image_url,
            'storage_path': relative_path,
            'original_url': image_url,
        }

    response = requests.get(image_url, timeout=timeout)
    response.raise_for_status()
    image_content = response.content
    extension = get_image_extension(
        content_type=response.headers.get('Content-Type', ''),
        source_url=image_url,
        content=image_content,
    )
    filename = f'image_{uuid.uuid4().hex}{extension}'
    _, relative_path = image_storage.save_file(filename=filename, content=image_content)
    return {
        'url': build_storage_url(relative_path),
        'storage_path': relative_path,
        'original_url': image_url,
    }


def save_b64_image_to_storage(b64_json: str) -> dict:
    image_content = base64.b64decode(b64_json)
    extension = get_image_extension(content=image_content)
    filename = f'image_{uuid.uuid4().hex}{extension}'
    _, relative_path = image_storage.save_file(filename=filename, content=image_content)
    return {
        'url': build_storage_url(relative_path),
        'storage_path': relative_path,
        'original_url': '',
    }


def image_item_from_data_url(data_url: str) -> dict:
    """将 data:image/...;base64,... 转成统一的 b64_json 图片项。"""
    if not isinstance(data_url, str):
        return {}

    value = data_url.strip()
    if not value.startswith('data:image/') or ';base64,' not in value:
        return {}

    _, encoded = value.split(';base64,', 1)
    encoded = ''.join(encoded.split())
    if not encoded:
        return {}

    return {'b64_json': encoded, 'original_url': value}


def localize_image_item(item: dict, width: int, height: int, timeout: int) -> dict:
    """将单个图片结果本地化到统一存储。"""
    image_url = item.get('url', '')
    b64_json = item.get('b64_json', '')
    data_url_item = image_item_from_data_url(image_url)
    if data_url_item:
        image_url = ''
        b64_json = data_url_item['b64_json']

    localized = {
        'width': item.get('width', width),
        'height': item.get('height', height),
    }

    try:
        if image_url:
            localized.update(download_image_to_storage(image_url, timeout))
            return localized
        if b64_json:
            localized.update(save_b64_image_to_storage(b64_json))
            return localized
    except Exception as exc:
        if image_url:
            localized['url'] = image_url
            localized['original_url'] = image_url
            localized['download_error'] = str(exc)
            return localized
        localized['download_error'] = str(exc)
        return localized

    return localized


def image_item_from_value(value: Any) -> dict:
    """将单个返回值归一化为图片项。"""
    if not isinstance(value, str):
        return {}

    data_url_item = image_item_from_data_url(value)
    if data_url_item:
        return data_url_item

    if value.startswith('http://') or value.startswith('https://'):
        return {'url': value}

    return {}


def extract_image_items_from_content(content: Any) -> List[dict]:
    """从字符串或多段消息内容中提取图片结果项。"""
    if not content:
        return []

    if isinstance(content, str):
        items = []
        for candidate in IMAGE_MARKDOWN_PATTERN.findall(content):
            cleaned = candidate.strip()
            item = image_item_from_value(cleaned)
            if item:
                items.append(item)

        if items:
            return items

        for candidate in DATA_IMAGE_PATTERN.findall(content):
            item = image_item_from_value(candidate)
            if item:
                items.append(item)

        for candidate in URL_PATTERN.findall(content):
            cleaned = candidate.rstrip(').,]\n\r\t ')
            item = image_item_from_value(cleaned)
            if item:
                items.append(item)

        return items

    if isinstance(content, list):
        items: List[dict] = []
        for item in content:
            if not isinstance(item, dict):
                continue

            image_url = item.get('image_url')
            if isinstance(image_url, dict):
                normalized = image_item_from_value(image_url.get('url'))
                if normalized:
                    items.append(normalized)
            elif isinstance(image_url, str):
                normalized = image_item_from_value(image_url)
                if normalized:
                    items.append(normalized)

            direct_item = image_item_from_value(item.get('url'))
            if direct_item:
                items.append(direct_item)

            b64_json = item.get('b64_json')
            if isinstance(b64_json, str) and b64_json:
                items.append({'b64_json': ''.join(b64_json.split())})

            for key in ('text', 'content'):
                nested_text = item.get(key)
                if isinstance(nested_text, str):
                    items.extend(extract_image_items_from_content(nested_text))

        return items

    return []


def extract_image_urls_from_content(content: Any) -> List[str]:
    """从字符串或多段消息内容中提取图片 URL。"""
    if not content:
        return []

    if isinstance(content, str):
        urls = IMAGE_MARKDOWN_PATTERN.findall(content)
        if urls:
            return urls

        fallback_urls = []
        for candidate in URL_PATTERN.findall(content):
            cleaned = candidate.rstrip(').,]\n\r\t ')
            if cleaned:
                fallback_urls.append(cleaned)
        return fallback_urls

    if isinstance(content, list):
        urls: List[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            image_url = item.get('image_url')
            if isinstance(image_url, dict):
                value = image_url.get('url')
                if value:
                    urls.append(value)
            elif isinstance(image_url, str) and image_url:
                urls.append(image_url)

            direct_url = item.get('url')
            if isinstance(direct_url, str) and direct_url:
                urls.append(direct_url)

            for key in ('text', 'content'):
                nested_text = item.get(key)
                if isinstance(nested_text, str):
                    urls.extend(extract_image_urls_from_content(nested_text))
        return urls

    return []


def normalize_result_data(raw_items: Any) -> List[dict]:
    """将厂商响应中的 data 字段统一成 list[dict]。"""
    if raw_items is None:
        return []
    if isinstance(raw_items, dict):
        return [raw_items]
    if isinstance(raw_items, list):
        return [item for item in raw_items if isinstance(item, dict)]
    return []


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def merge_extra_payload(base_payload: dict, extra: dict, reserved_keys: Iterable[str]) -> dict:
    """合并额外参数，同时避免覆盖统一层的保留字段。"""
    reserved = set(reserved_keys)
    for key, value in (extra or {}).items():
        if key in reserved or value is None:
            continue
        base_payload[key] = value
    return base_payload
