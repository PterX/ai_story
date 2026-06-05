"""Helpers for preparing workflow image inputs for model APIs."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import unquote, urlparse

from django.conf import settings


STORAGE_IMAGE_PREFIX = '/api/v1/content/storage/image/'


def _is_online_url(value: str) -> bool:
    return value.startswith(('http://', 'https://'))


def _extract_url(value: Any, *, prefer_online_url: bool = False) -> str:
    if isinstance(value, dict):
        if prefer_online_url:
            for key in ('original_url', 'source_url'):
                candidate = str(value.get(key) or '').strip()
                if _is_online_url(candidate):
                    return candidate
        return str(value.get('url') or value.get('image_url') or value.get('imageUrl') or '').strip()
    return str(value or '').strip()


def _storage_relative_path(image_url: str) -> str:
    parsed_path = urlparse(image_url).path if image_url.startswith(('http://', 'https://')) else image_url
    if STORAGE_IMAGE_PREFIX not in parsed_path:
        return ''
    return unquote(parsed_path.split(STORAGE_IMAGE_PREFIX, 1)[1]).lstrip('/')


def _storage_image_path(image_url: str) -> Path:
    relative_path = _storage_relative_path(image_url)
    if not relative_path:
        return Path()

    image_root = (Path(settings.STORAGE_ROOT) / 'image').resolve()
    image_path = (image_root / relative_path).resolve()
    if image_root not in image_path.parents and image_path != image_root:
        raise RuntimeError('本地图片路径不合法，无法读取')
    return image_path


def is_storage_image_url(value: Any) -> bool:
    return bool(_storage_relative_path(_extract_url(value)))


def _guess_image_mime_type(image_url: str, image_bytes: bytes = b'') -> str:
    guessed_type, _ = mimetypes.guess_type(urlparse(image_url).path or image_url)
    if guessed_type and guessed_type.startswith('image/'):
        return guessed_type

    if image_bytes.startswith(b'\xFF\xD8\xFF'):
        return 'image/jpeg'
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if image_bytes.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:16]:
        return 'image/webp'
    if image_bytes.startswith(b'BM'):
        return 'image/bmp'
    if image_bytes.lstrip().startswith(b'<svg'):
        return 'image/svg+xml'
    return 'image/jpeg'


def encode_storage_image(image_url: str) -> Dict[str, str]:
    image_path = _storage_image_path(image_url)
    if not image_path:
        return {}
    if not image_path.exists() or not image_path.is_file():
        raise RuntimeError(f'本地图片不存在，无法读取: {image_url}')

    image_bytes = image_path.read_bytes()
    mime_type = _guess_image_mime_type(image_url, image_bytes)
    encoded = base64.b64encode(image_bytes).decode('utf-8')
    return {
        'source_url': image_url,
        'base64': encoded,
        'mime_type': mime_type,
        'data_url': f'data:{mime_type};base64,{encoded}',
    }


def _base64_from_data_url(value: str) -> Dict[str, str]:
    if not value.startswith('data:') or ';base64,' not in value:
        return {}
    header, encoded = value.split(';base64,', 1)
    mime_type = header[5:] or 'image/jpeg'
    return {
        'source_url': value,
        'base64': encoded,
        'mime_type': mime_type,
        'data_url': value,
    }


def prepare_image_inputs_for_api(image_inputs: Iterable[Any], *, prefer_online_url: bool = False) -> Dict[str, Any]:
    """Convert local storage image URLs into base64 data URLs for model APIs."""
    original_urls: List[str] = []
    api_image_inputs: List[str] = []
    image_base64s: List[str] = []
    mime_types: List[str] = []

    for item in image_inputs or []:
        image_url = _extract_url(item, prefer_online_url=prefer_online_url)
        if not image_url:
            continue

        original_urls.append(image_url)
        encoded_payload = _base64_from_data_url(image_url)
        if not encoded_payload and is_storage_image_url(image_url):
            encoded_payload = encode_storage_image(image_url)

        if encoded_payload:
            api_image_inputs.append(encoded_payload['data_url'])
            image_base64s.append(encoded_payload['base64'])
            mime_types.append(encoded_payload['mime_type'])
        else:
            api_image_inputs.append(image_url)

    deduped_original_urls = list(dict.fromkeys(original_urls))
    deduped_api_inputs = list(dict.fromkeys(api_image_inputs))
    deduped_base64s = list(dict.fromkeys(image_base64s))
    return {
        'original_urls': deduped_original_urls,
        'api_image_inputs': deduped_api_inputs,
        'image_base64s': deduped_base64s,
        'image_mime_type': mime_types[0] if mime_types else '',
    }
