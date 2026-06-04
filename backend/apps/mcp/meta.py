import sys

import django
import rest_framework

from apps.mcp.auth import get_mcp_access_token
from apps.mcp.registry import list_tool_groups


def get_mcp_module_plan():
    return [
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
