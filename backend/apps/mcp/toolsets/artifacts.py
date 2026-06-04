import json
import uuid

from django.conf import settings
from django.utils import timezone

from core.utils.file_storage import DateBasedFileStorage

from apps.mcp.errors import MCPToolError


def _public_storage_url(relative_path):
    storage_url = (getattr(settings, 'STORAGE_URL', 'storage/') or 'storage/').strip('/')
    return f'/{storage_url}/{relative_path.lstrip("/")}'


def save_artifact(arguments):
    artifact_type = (arguments.get('type') or 'json').strip()
    title = (arguments.get('title') or 'Agent 产物').strip()
    data = arguments.get('data')
    url = (arguments.get('url') or '').strip()
    metadata = arguments.get('metadata') or {}

    if data is None and not url:
        raise MCPToolError('缺少 data 或 url')

    artifact = {
        'id': f'artifact-{uuid.uuid4().hex[:10]}',
        'type': artifact_type,
        'title': title,
        'url': url,
        'data': data,
        'metadata': metadata,
        'created_at': timezone.now().isoformat(),
    }

    storage = DateBasedFileStorage('agent/artifacts')
    filename = f'{artifact["id"]}.json'
    _, relative_path = storage.save_file(
        filename,
        json.dumps(artifact, ensure_ascii=False, indent=2).encode('utf-8'),
    )
    artifact['artifact_url'] = _public_storage_url(f'agent/artifacts/{relative_path}')
    return {'artifact': artifact}


TOOL_DEFINITIONS = [
    {
        'name': 'artifact.save',
        'description': '保存 agent 生成的结构化产物，并返回前端可渲染的 artifact 对象。',
        'inputSchema': {
            'type': 'object',
            'required': ['type', 'title'],
            'properties': {
                'type': {'type': 'string', 'description': 'text、image、poster_plan、json 等'},
                'title': {'type': 'string'},
                'url': {'type': 'string'},
                'data': {
                    'description': '任意可 JSON 序列化的产物数据，可为对象、数组或字符串。',
                },
                'metadata': {'type': 'object'},
            },
        },
        'handler': save_artifact,
    },
]
