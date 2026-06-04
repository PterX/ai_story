from apps.mcp.errors import MCPToolError
from apps.workflows.node_executors.execute_image_generation import execute_image_generation


def _normalize_ratio(value):
    """"""
    ratio = (value or '').strip()
    allowed = {'1:1', '3:4', '4:3', '9:16', '16:9'}
    return ratio if ratio in allowed else '1:1'


def generate_image(arguments):
    prompt = (arguments.get('prompt') or '').strip()
    if not prompt:
        raise MCPToolError('缺少 prompt')

    payload = {
        'prompt': prompt,
        'negative_prompt': arguments.get('negative_prompt') or '',
        'aspect_ratio': _normalize_ratio(arguments.get('aspect_ratio') or arguments.get('ratio')),
        'sample_count': arguments.get('sample_count') or arguments.get('n') or 1,
        'model': arguments.get('model') or '',
        'resolution': arguments.get('resolution') or '2k',
    }

    for key in ['width', 'height', 'size', 'seed', 'image', 'images', 'source_images', 'source_image_url']:
        if arguments.get(key) not in (None, ''):
            payload[key] = arguments.get(key)

    result = execute_image_generation(payload)
    normalized = result.get('normalized_output') or {}
    return {
        'artifact': {
            'type': 'image',
            'title': arguments.get('title') or 'AI 生成图片',
            'url': normalized.get('image_url') or normalized.get('imageUrl') or '',
            'prompt': prompt,
            'metadata': {
                'aspect_ratio': payload['aspect_ratio'],
                'model': normalized.get('model') or payload.get('model') or '',
                'resolution': normalized.get('resolution') or payload.get('resolution') or '',
            },
        },
        'raw': result.get('output_payload') or {},
        'normalized': normalized,
    }


TOOL_DEFINITIONS = [
    {
        'name': 'image.generate',
        'description': '根据图片提示词生成图片，返回可展示的 image artifact。',
        'inputSchema': {
            'type': 'object',
            'required': ['prompt'],
            'properties': {
                'prompt': {'type': 'string', 'description': '图片生成提示词'},
                'negative_prompt': {'type': 'string'},
                'aspect_ratio': {'type': 'string', 'enum': ['1:1', '3:4', '4:3', '9:16', '16:9']},
                'sample_count': {'type': 'integer', 'default': 1},
                'model': {'type': 'string'},
                'resolution': {'type': 'string', 'default': '2k'},
                'title': {'type': 'string'},
                'source_image_url': {'type': 'string'},
            },
        },
        'handler': generate_image,
    },
]
