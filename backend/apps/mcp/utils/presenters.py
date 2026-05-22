def mask_secret(value, visible=4):
    text = (value or '').strip()
    if not text:
        return ''
    if len(text) <= visible:
        return '*' * len(text)
    return '*' * (len(text) - visible) + text[-visible:]


def tool_text_payload(data, is_error=False):
    import json

    return {
        'content': [
            {
                'type': 'text',
                'text': json.dumps(data, ensure_ascii=False, indent=2),
            }
        ],
        'structuredContent': data,
        'isError': is_error,
    }

