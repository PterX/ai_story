from apps.mcp.toolsets.content import TOOL_DEFINITIONS as CONTENT_TOOL_DEFINITIONS
from apps.mcp.toolsets.models import TOOL_DEFINITIONS as MODELS_TOOL_DEFINITIONS
from apps.mcp.toolsets.prompt_mutation import TOOL_DEFINITIONS as PROMPT_MUTATION_TOOL_DEFINITIONS
from apps.mcp.toolsets.projects import TOOL_DEFINITIONS as PROJECTS_TOOL_DEFINITIONS
from apps.mcp.toolsets.prompts import TOOL_DEFINITIONS as PROMPTS_TOOL_DEFINITIONS


TOOLSET_GROUPS = [
    {
        'key': 'projects',
        'name': '项目管理',
        'description': '项目、阶段、作品与统计查询工具。',
        'tools': PROJECTS_TOOL_DEFINITIONS,
    },
    {
        'key': 'content',
        'name': '内容操作',
        'description': '文案改写、分镜、运镜的读取与修改工具。',
        'tools': CONTENT_TOOL_DEFINITIONS,
    },
    {
        'key': 'prompts',
        'name': '提示词管理',
        'description': '提示词集、模板和变量查询工具。',
        'tools': PROMPTS_TOOL_DEFINITIONS,
    },
    {
        'key': 'prompt_mutation',
        'name': '提示词修改',
        'description': '提示词模板、提示词集和调试草稿的受控修改工具。',
        'tools': PROMPT_MUTATION_TOOL_DEFINITIONS,
    },
    {
        'key': 'models',
        'name': '模型管理',
        'description': '模型提供商和调用日志查询工具。',
        'tools': MODELS_TOOL_DEFINITIONS,
    },
]

TOOL_DEFINITIONS = PROJECTS_TOOL_DEFINITIONS + CONTENT_TOOL_DEFINITIONS + PROMPTS_TOOL_DEFINITIONS + PROMPT_MUTATION_TOOL_DEFINITIONS + MODELS_TOOL_DEFINITIONS
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
