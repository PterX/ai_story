from apps.mcp.errors import MCPToolError
from apps.mcp.services import prompt_mutation_service


def _require_found(data, label):
    if data is None:
        raise MCPToolError('{label}不存在'.format(label=label))
    return data


def update_prompt_template(arguments):
    template_id = (arguments.get('template_id') or '').strip()
    if not template_id:
        raise MCPToolError('缺少 template_id')
    updates = {}
    for field in ['template_set', 'stage_type', 'model_provider', 'template_content', 'variables', 'client_params', 'is_active']:
        if field in arguments:
            updates[field] = arguments.get(field)
    return _require_found(prompt_mutation_service.update_prompt_template(template_id, updates), '提示词模板')


def create_prompt_template_version(arguments):
    template_id = (arguments.get('template_id') or '').strip()
    if not template_id:
        raise MCPToolError('缺少 template_id')
    return _require_found(prompt_mutation_service.create_prompt_template_version(template_id, arguments), '提示词模板')


def update_prompt_template_set(arguments):
    template_set_id = (arguments.get('template_set_id') or '').strip()
    if not template_set_id:
        raise MCPToolError('缺少 template_set_id')
    updates = {}
    for field in ['name', 'description', 'is_active', 'is_default']:
        if field in arguments:
            updates[field] = arguments.get(field)
    return _require_found(prompt_mutation_service.update_prompt_template_set(template_set_id, updates), '提示词集')


def set_default_prompt_template_set(arguments):
    template_set_id = (arguments.get('template_set_id') or '').strip()
    if not template_set_id:
        raise MCPToolError('缺少 template_set_id')
    return _require_found(prompt_mutation_service.set_default_prompt_template_set(template_set_id), '提示词集')


def save_prompt_debug_session_to_template(arguments):
    session_id = (arguments.get('session_id') or '').strip()
    if not session_id:
        raise MCPToolError('缺少 session_id')
    payload = {
        'template_content': arguments.get('template_content') or '',
        'variables': arguments.get('variables') or {},
        'client_params': arguments.get('client_params') or {},
    }
    if 'model_provider_id' in arguments:
        payload['model_provider_id'] = arguments.get('model_provider_id')
    return _require_found(prompt_mutation_service.save_prompt_debug_session_to_template(session_id, payload, as_version=False), '调试会话')


def save_prompt_debug_session_as_version(arguments):
    session_id = (arguments.get('session_id') or '').strip()
    if not session_id:
        raise MCPToolError('缺少 session_id')
    payload = {
        'template_content': arguments.get('template_content') or '',
        'variables': arguments.get('variables') or {},
        'client_params': arguments.get('client_params') or {},
    }
    if 'model_provider_id' in arguments:
        payload['model_provider_id'] = arguments.get('model_provider_id')
    return _require_found(prompt_mutation_service.save_prompt_debug_session_to_template(session_id, payload, as_version=True), '调试会话')


TOOL_DEFINITIONS = [
    {
        'name': 'update_prompt_template',
        'description': '更新提示词模板内容、变量、模型或执行参数。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_id'],
            'properties': {
                'template_id': {'type': 'string'},
                'template_set': {'type': 'string'},
                'stage_type': {'type': 'string'},
                'model_provider': {'type': ['string', 'null']},
                'template_content': {'type': 'string'},
                'variables': {'type': 'object'},
                'client_params': {'type': 'object'},
                'is_active': {'type': 'boolean'},
            },
        },
        'handler': update_prompt_template,
    },
    {
        'name': 'create_prompt_template_version',
        'description': '基于现有模板创建新版本，并停用旧版本。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_id'],
            'properties': {
                'template_id': {'type': 'string'},
                'template_content': {'type': 'string'},
                'variables': {'type': 'object'},
                'client_params': {'type': 'object'},
                'model_provider': {'type': ['string', 'null']},
            },
        },
        'handler': create_prompt_template_version,
    },
    {
        'name': 'update_prompt_template_set',
        'description': '更新提示词集基础信息。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_set_id'],
            'properties': {
                'template_set_id': {'type': 'string'},
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'is_active': {'type': 'boolean'},
                'is_default': {'type': 'boolean'},
            },
        },
        'handler': update_prompt_template_set,
    },
    {
        'name': 'set_default_prompt_template_set',
        'description': '将指定提示词集设为默认。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_set_id'],
            'properties': {'template_set_id': {'type': 'string'}},
        },
        'handler': set_default_prompt_template_set,
    },
    {
        'name': 'save_prompt_debug_session_to_template',
        'description': '将调试会话草稿保存回模板。',
        'inputSchema': {
            'type': 'object',
            'required': ['session_id', 'template_content'],
            'properties': {
                'session_id': {'type': 'string'},
                'template_content': {'type': 'string'},
                'variables': {'type': 'object'},
                'client_params': {'type': 'object'},
                'model_provider_id': {'type': ['string', 'null']},
            },
        },
        'handler': save_prompt_debug_session_to_template,
    },
    {
        'name': 'save_prompt_debug_session_as_version',
        'description': '将调试会话草稿保存为模板新版本。',
        'inputSchema': {
            'type': 'object',
            'required': ['session_id', 'template_content'],
            'properties': {
                'session_id': {'type': 'string'},
                'template_content': {'type': 'string'},
                'variables': {'type': 'object'},
                'client_params': {'type': 'object'},
                'model_provider_id': {'type': ['string', 'null']},
            },
        },
        'handler': save_prompt_debug_session_as_version,
    },
]
