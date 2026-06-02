"""音频节点执行逻辑。"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict


def execute_audio(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行音频节点。

    当前先支持“已存在音频资产直通”模式：
    - 前端上传音频到 ai_story 文件服务后，将返回的 URL 作为 audio_url 传入
    - 工作流节点执行时仅做参数校验和结果标准化，纳入统一状态流

    后续可在此基础上扩展为真实 TTS / 音乐生成。
    """

    audio_url = (
        input_payload.get('audio_url')
        or input_payload.get('audioUrl')
        or ''
    ).strip()
    prompt = (input_payload.get('prompt') or '').strip()
    model = (input_payload.get('model') or '').strip()
    duration = input_payload.get('audio_duration') or input_payload.get('audioDuration') or '10s'
    source_text = (input_payload.get('text') or input_payload.get('source_text') or '').strip()

    if not audio_url:
        raise RuntimeError('缺少 audio_url，当前版本仅支持已上传音频资产执行')

    output_payload = {
        'id': f'audgen-{uuid.uuid4().hex[:8]}',
        'object': 'audio.asset',
        'created': int(time.time()),
        'data': [{
            'url': audio_url,
            'audio_url': audio_url,
        }],
        'metadata': {
            'source': 'uploaded-audio',
        },
    }

    normalized_output = {
        'audioUrl': audio_url,
        'audio_url': audio_url,
        'prompt': prompt,
        'model': model,
        'audioDuration': duration,
        'audio_duration': duration,
        'text': source_text,
        'source': 'uploaded-audio',
    }

    return {
        'output_payload': output_payload,
        'normalized_output': normalized_output,
    }
