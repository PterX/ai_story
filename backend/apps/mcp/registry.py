from apps.mcp.toolsets.artifacts import TOOL_DEFINITIONS as ARTIFACT_TOOL_DEFINITIONS
from apps.mcp.toolsets.image import TOOL_DEFINITIONS as IMAGE_TOOL_DEFINITIONS
from apps.mcp.toolsets.linknow import TOOL_DEFINITIONS as LINKNOW_TOOL_DEFINITIONS


TOOLSET_GROUPS = [
    {
        'key': 'linknow',
        'name': 'Linknow 创作上下文',
        'description': 'Linknow 创作场景、页面上下文与默认交付规格。',
        'tools': LINKNOW_TOOL_DEFINITIONS,
    },
    {
        'key': 'image',
        'name': '图片生成',
        'description': '面向 agent 的文生图与图片产物生成工具。',
        'tools': IMAGE_TOOL_DEFINITIONS,
    },
    {
        'key': 'artifacts',
        'name': '产物保存',
        'description': '保存并返回前端可渲染的 agent 产物。',
        'tools': ARTIFACT_TOOL_DEFINITIONS,
    }
]

TOOL_DEFINITIONS = (
    LINKNOW_TOOL_DEFINITIONS
    + IMAGE_TOOL_DEFINITIONS
    + ARTIFACT_TOOL_DEFINITIONS
)
TOOLS_BY_NAME = {item['name']: item for item in TOOL_DEFINITIONS}


def list_tools():
    return [
        {
            'name': item['name'],
            'description': item['description'],
            'inputSchema': item['inputSchema'],
        }
        for item in TOOL_DEFINITIONS
    ]


def list_tool_groups():
    return [
        {
            'key': group['key'],
            'name': group['name'],
            'description': group['description'],
            'tool_count': len(group['tools']),
            'tools': [
                {
                    'name': item['name'],
                    'description': item['description'],
                    'inputSchema': item['inputSchema'],
                }
                for item in group['tools']
            ],
        }
        for group in TOOLSET_GROUPS
    ]


def call_tool(name, arguments=None):
    from apps.mcp.errors import MCPToolError

    tool = TOOLS_BY_NAME.get(name)
    if not tool:
        raise MCPToolError(f'未找到工具: {name}')
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise MCPToolError('arguments 必须是对象')
    return tool['handler'](arguments)
