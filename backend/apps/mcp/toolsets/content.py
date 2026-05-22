from apps.mcp.errors import MCPToolError
from apps.mcp.services import content_service


def _require_found(data, label):
    if data is None:
        raise MCPToolError(f'{label}不存在')
    return data


def get_rewrite_content(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return _require_found(content_service.get_rewrite_content(project_id), '文案改写')


def update_rewrite_content(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    rewritten_text = arguments.get('rewritten_text')
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if rewritten_text is None:
        raise MCPToolError('缺少 rewritten_text')
    return content_service.update_rewrite_content(
        project_id,
        rewritten_text=rewritten_text,
        original_text=arguments.get('original_text'),
    )


def list_storyboards(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    return content_service.list_storyboards(project_id)


def get_storyboard_detail(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    storyboard_id = (arguments.get('storyboard_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if not storyboard_id:
        raise MCPToolError('缺少 storyboard_id')
    return _require_found(
        content_service.get_storyboard_detail(project_id, storyboard_id),
        '分镜',
    )


def update_storyboard(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    storyboard_id = (arguments.get('storyboard_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if not storyboard_id:
        raise MCPToolError('缺少 storyboard_id')
    return content_service.update_storyboard(
        project_id,
        storyboard_id,
        scene_description=arguments.get('scene_description'),
        narration_text=arguments.get('narration_text'),
        image_prompt=arguments.get('image_prompt'),
        duration_seconds=arguments.get('duration_seconds'),
    )


def get_camera_movement(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    camera_id = (arguments.get('camera_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if not camera_id:
        raise MCPToolError('缺少 camera_id')
    return _require_found(
        content_service.get_camera_movement(project_id, camera_id),
        '运镜',
    )


def update_camera_movement(arguments):
    project_id = (arguments.get('project_id') or '').strip()
    camera_id = (arguments.get('camera_id') or '').strip()
    if not project_id:
        raise MCPToolError('缺少 project_id')
    if not camera_id:
        raise MCPToolError('缺少 camera_id')
    return content_service.update_camera_movement(
        project_id,
        camera_id,
        movement_type=arguments.get('movement_type'),
        movement_params=arguments.get('movement_params'),
    )


TOOL_DEFINITIONS = [
    {
        'name': 'get_rewrite_content',
        'description': '获取项目的文案改写内容，包括原始文本和改写后的文本。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
            },
        },
        'handler': get_rewrite_content,
    },
    {
        'name': 'update_rewrite_content',
        'description': '更新项目的文案改写内容。修改后请通知前端刷新画布。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'rewritten_text'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
                'rewritten_text': {'type': 'string', 'description': '改写后的文案内容'},
                'original_text': {'type': 'string', 'description': '原始文本（可选，仅在首次创建时使用项目的 original_topic）'},
            },
        },
        'handler': update_rewrite_content,
    },
    {
        'name': 'list_storyboards',
        'description': '列出项目的所有分镜，包括场景描述、旁白、图片prompt、运镜和已生成的图片。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
            },
        },
        'handler': list_storyboards,
    },
    {
        'name': 'get_storyboard_detail',
        'description': '获取单个分镜的详细信息。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'storyboard_id'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
                'storyboard_id': {'type': 'string', 'description': '分镜ID'},
            },
        },
        'handler': get_storyboard_detail,
    },
    {
        'name': 'update_storyboard',
        'description': '更新分镜内容，可修改场景描述、旁白文案、文生图提示词或时长。修改后请通知前端刷新画布。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'storyboard_id'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
                'storyboard_id': {'type': 'string', 'description': '分镜ID'},
                'scene_description': {'type': 'string', 'description': '场景描述'},
                'narration_text': {'type': 'string', 'description': '旁白文案'},
                'image_prompt': {'type': 'string', 'description': '文生图提示词'},
                'duration_seconds': {'type': 'number', 'description': '时长（秒）'},
            },
        },
        'handler': update_storyboard,
    },
    {
        'name': 'get_camera_movement',
        'description': '获取分镜的运镜参数。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'camera_id'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
                'camera_id': {'type': 'string', 'description': '运镜ID'},
            },
        },
        'handler': get_camera_movement,
    },
    {
        'name': 'update_camera_movement',
        'description': '更新分镜的运镜参数，可修改运镜类型或运镜参数。修改后请通知前端刷新画布。',
        'inputSchema': {
            'type': 'object',
            'required': ['project_id', 'camera_id'],
            'properties': {
                'project_id': {'type': 'string', 'description': '项目ID'},
                'camera_id': {'type': 'string', 'description': '运镜ID'},
                'movement_type': {
                    'type': 'string',
                    'description': '运镜类型',
                    'enum': ['static', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'tilt_up', 'tilt_down', 'dolly_in', 'dolly_out'],
                },
                'movement_params': {'type': 'object', 'description': '运镜参数（JSON对象）'},
            },
        },
        'handler': update_camera_movement,
    },
]
