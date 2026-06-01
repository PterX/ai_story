"""LLM 客户端流式调用辅助函数。"""

import time
from typing import Any, Dict


def collect_llm_stream_text(
    client,
    *,
    user_prompt: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
    top_p: float = 1.0,
) -> Dict[str, Any]:
    """通过流式接口收集 LLM 生成的完整文本。"""
    full_text = ''
    response_metadata: Dict[str, Any] = {}
    start_time = time.time()
    stream = client.generate_stream(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    for chunk in stream:
        chunk_type = chunk.get('type')
        if chunk_type == 'token':
            full_text = chunk.get('full_text', full_text + chunk.get('content', ''))
            continue
        if chunk_type == 'done':
            full_text = chunk.get('full_text', full_text)
            response_metadata = chunk.get('metadata') or {}
            break
        if chunk_type == 'error':
            raise RuntimeError(chunk.get('error') or '分镜流式生成失败')

    latency_ms = response_metadata.get('latency_ms') or int((time.time() - start_time) * 1000)
    return {
        'text': full_text,
        'latency_ms': latency_ms,
        'metadata': response_metadata,
    }
