from apps.mcp.errors import MCPToolError
from apps.mcp.services import models_service
from apps.mcp.utils.common import to_bool, to_int


def _require_found(data, label):
    if data is None:
        raise MCPToolError(f'{label}不存在')
    return data


def list_model_providers(arguments):
    raw_is_active = arguments.get('is_active')
    is_active = None if raw_is_active in (None, '') else to_bool(raw_is_active)
    return models_service.list_model_providers(
        provider_type=(arguments.get('provider_type') or '').strip(),
        is_active=is_active,
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


def get_model_provider_detail(arguments):
    provider_id = (arguments.get('provider_id') or '').strip()
    if not provider_id:
        raise MCPToolError('缺少 provider_id')
    return _require_found(models_service.get_model_provider_detail(provider_id), '模型提供商')


def list_model_usage_logs(arguments):
    return models_service.list_model_usage_logs(
        project_id=(arguments.get('project_id') or '').strip(),
        stage_type=(arguments.get('stage_type') or '').strip(),
        status=(arguments.get('status') or '').strip(),
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


TOOL_DEFINITIONS = [
    {
        'name': 'list_model_providers',
        'description': '列出模型提供商。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'provider_type': {'type': 'string'},
                'is_active': {'type': 'boolean'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_model_providers,
    },
    {
        'name': 'get_model_provider_detail',
        'description': '查询模型提供商详情，敏感密钥字段会脱敏。',
        'inputSchema': {
            'type': 'object',
            'required': ['provider_id'],
            'properties': {'provider_id': {'type': 'string'}},
        },
        'handler': get_model_provider_detail,
    },
    {
        'name': 'list_model_usage_logs',
        'description': '查询模型调用日志。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_id': {'type': 'string'},
                'stage_type': {'type': 'string'},
                'status': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_model_usage_logs,
    },
]

