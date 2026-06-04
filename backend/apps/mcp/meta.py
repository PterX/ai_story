import sys

import django
import rest_framework

from apps.mcp.auth import get_mcp_access_token
from apps.mcp.registry import list_tool_groups


def get_mcp_module_plan():
    return [
        {
            'key': 'linknow',
            'name': 'Linknow 创作上下文',
            'phase': 1,
            'status': 'ready',
            'risk_level': 'low',
            'candidate_tools': [
                'linknow.get_context',
            ],
        },
        {
            'key': 'image',
            'name': '图片生成',
            'phase': 1,
            'status': 'ready',
            'risk_level': 'medium',
            'candidate_tools': [
                'image.generate',
            ],
        },
        {
            'key': 'artifacts',
            'name': '产物保存',
            'phase': 1,
            'status': 'ready',
            'risk_level': 'low',
            'candidate_tools': [
                'artifact.save',
            ],
        },
        {
            'key': 'projects',
            'name': '项目与作品查询',
            'phase': 1,
            'status': 'ready',
            'risk_level': 'low',
            'candidate_tools': [
                'list_projects',
                'get_project_detail',
                'get_project_stages',
                'list_series',
                'get_series_detail',
                'get_project_statistics',
            ],
        },
        {
            'key': 'prompts',
            'name': '提示词与变量查询',
            'phase': 1,
            'status': 'ready',
            'risk_level': 'low',
            'candidate_tools': [
                'list_prompt_template_sets',
                'get_prompt_template_set_detail',
                'list_prompt_templates',
                'get_prompt_template_detail',
                'preview_prompt_template',
                'list_global_variables',
            ],
        },
        {
            'key': 'prompt_mutation',
            'name': '提示词修改',
            'phase': 2,
            'status': 'partial',
            'risk_level': 'medium',
            'candidate_tools': [
                'update_prompt_template',
                'create_prompt_template_version',
                'update_prompt_template_set',
                'set_default_prompt_template_set',
                'save_prompt_debug_session_to_template',
                'save_prompt_debug_session_as_version',
            ],
        },
        {
            'key': 'models',
            'name': '模型与日志查询',
            'phase': 1,
            'status': 'ready',
            'risk_level': 'medium',
            'candidate_tools': [
                'list_model_providers',
                'get_model_provider_detail',
                'list_model_usage_logs',
            ],
        },
        {
            'key': 'mutations',
            'name': '受控任务操作',
            'phase': 2,
            'status': 'partial',
            'risk_level': 'medium',
            'candidate_tools': [
                'run_project_pipeline',
                'pause_project',
                'resume_project',
                'execute_project_stage',
                'get_project_task_status',
            ],
        },
    ]


def get_mcp_runtime_report():
    return {
        'ready': bool(get_mcp_access_token()),
        'status': 'ready' if get_mcp_access_token() else 'blocked',
        'current_runtime': {
            'python': '.'.join(str(i) for i in sys.version_info[:3]),
            'django': django.get_version(),
            'djangorestframework': getattr(rest_framework, '__version__', 'unknown'),
        },
        'endpoints': {
            'rpc': '/mcp/',
            'meta': '/mcp/meta/',
        },
        'native_server': {
            'enabled': True,
            'type': 'jsonrpc_http',
            'auth': 'bearer_token',
            'methods': ['initialize', 'ping', 'tools/list', 'tools/call'],
        },
        'tool_groups': list_tool_groups(),
        'planned_modules': get_mcp_module_plan(),
        'blocking_reasons': [] if get_mcp_access_token() else ['未配置 MCP_ACCESS_TOKEN 或 AGENT_SERVER_PASSWORD'],
        'next_steps': [
            '使用 Authorization: Bearer <token> 调用 /mcp/。',
            '如需从 AGENT_SERVER_PASSWORD 解耦，可单独配置 MCP_ACCESS_TOKEN。',
        ],
    }
