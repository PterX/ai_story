from apps.mcp.errors import MCPToolError
from apps.mcp.services import prompts_service
from apps.mcp.utils.common import to_int


def _require_found(data, label):
    if data is None:
        raise MCPToolError(f'{label}不存在')
    return data


def list_prompt_template_sets(arguments):
    return prompts_service.list_prompt_template_sets(
        query=(arguments.get('query') or '').strip(),
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


def get_prompt_template_set_detail(arguments):
    template_set_id = (arguments.get('template_set_id') or '').strip()
    if not template_set_id:
        raise MCPToolError('缺少 template_set_id')
    return _require_found(prompts_service.get_prompt_template_set_detail(template_set_id), '提示词集')


def list_prompt_templates(arguments):
    return prompts_service.list_prompt_templates(
        template_set_id=(arguments.get('template_set_id') or '').strip(),
        stage_type=(arguments.get('stage_type') or '').strip(),
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


def get_prompt_template_detail(arguments):
    template_id = (arguments.get('template_id') or '').strip()
    if not template_id:
        raise MCPToolError('缺少 template_id')
    return _require_found(prompts_service.get_prompt_template_detail(template_id), '提示词模板')


def preview_prompt_template(arguments):
    template_id = (arguments.get('template_id') or '').strip()
    if not template_id:
        raise MCPToolError('缺少 template_id')
    return _require_found(prompts_service.preview_prompt_template(template_id, arguments.get('variables') or {}), '提示词模板')


def list_global_variables(arguments):
    return prompts_service.list_global_variables(
        query=(arguments.get('query') or '').strip(),
        group=(arguments.get('group') or '').strip(),
        scope=(arguments.get('scope') or '').strip(),
        limit=to_int(arguments.get('limit'), default=20, minimum=1, maximum=100),
    )


TOOL_DEFINITIONS = [
    {
        'name': 'list_prompt_template_sets',
        'description': '列出提示词集。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_prompt_template_sets,
    },
    {
        'name': 'get_prompt_template_set_detail',
        'description': '查询单个提示词集详情。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_set_id'],
            'properties': {'template_set_id': {'type': 'string'}},
        },
        'handler': get_prompt_template_set_detail,
    },
    {
        'name': 'list_prompt_templates',
        'description': '列出提示词模板，支持按提示词集和阶段过滤。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'template_set_id': {'type': 'string'},
                'stage_type': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_prompt_templates,
    },
    {
        'name': 'get_prompt_template_detail',
        'description': '查询单个提示词模板详情。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_id'],
            'properties': {'template_id': {'type': 'string'}},
        },
        'handler': get_prompt_template_detail,
    },
    {
        'name': 'preview_prompt_template',
        'description': '渲染提示词模板并返回预览结果。',
        'inputSchema': {
            'type': 'object',
            'required': ['template_id'],
            'properties': {
                'template_id': {'type': 'string'},
                'variables': {'type': 'object', 'default': {}},
            },
        },
        'handler': preview_prompt_template,
    },
    {
        'name': 'list_global_variables',
        'description': '列出全局变量。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'group': {'type': 'string'},
                'scope': {'type': 'string'},
                'limit': {'type': 'integer', 'default': 20},
            },
        },
        'handler': list_global_variables,
    },
]

