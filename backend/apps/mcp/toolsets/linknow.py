from django.utils import timezone


def get_linknow_context(arguments):
    scene = (arguments.get('scene') or 'poster_creation').strip()
    page = (arguments.get('page') or '').strip()
    user_goal = (arguments.get('user_goal') or '').strip()
    ui_context = arguments.get('ui_context') or {}

    return {
        'app': 'linknow',
        'scene': scene,
        'page': page,
        'user_goal': user_goal,
        'ui_context': ui_context,
        'defaults': {
            'poster_creation': {
                'platforms': ['朋友圈', '小红书'],
                'aspect_ratios': ['1:1', '3:4', '9:16'],
                'style': '高级、清晰、适合社交媒体发布',
                'deliverables': ['创意方向', '海报文案', '图片提示词', '图片产物'],
            },
        }.get(scene, {}),
        'timestamp': timezone.now().isoformat(),
    }


TOOL_DEFINITIONS = [
    {
        'name': 'linknow.get_context',
        'description': '获取 linknow 当前创作场景的上下文、默认输出规格和前端传入的 UI 信息。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'scene': {'type': 'string', 'default': 'poster_creation'},
                'page': {'type': 'string'},
                'user_goal': {'type': 'string'},
                'ui_context': {'type': 'object'},
            },
        },
        'handler': get_linknow_context,
    },
]
