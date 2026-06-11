"""分镜节点执行逻辑。"""

import time
import uuid
from typing import Any, Dict

import requests

from apps.ai_proxy.views import _build_provider_payload, _parse_float, _parse_int, _pick_provider
from apps.projects.utils import parse_storyboard_json
from apps.models.token_utils import create_ai_client_for_user

from ..models import WorkflowNodeRun
from .llm_helpers import collect_llm_stream_text
from .response_helpers import extract_assistant_text
from .template_helpers import render_storyboard_system_prompt, resolve_storyboard_template


def _normalize_storyboard_scene(scene: Dict[str, Any], fallback_index: int) -> Dict[str, Any]:
    """将原始分镜数据归一化为标准格式。"""
    sequence_number = _parse_int(scene.get('scene_number'), fallback_index) or fallback_index
    narration_text = (scene.get('narration') or '').strip()
    image_prompt = (scene.get('visual_prompt') or '').strip()
    shot_type = (scene.get('shot_type') or '').strip()

    return {
        'sequence_number': sequence_number,
        'scene_description': shot_type,
        'narration_text': narration_text,
        'image_prompt': image_prompt,
        'duration_seconds': _parse_float(scene.get('duration'), 3.0) or 3.0,
        'generation_metadata': {
            'shot_type': shot_type,
            'raw_scene_data': scene,
        },
    }


def execute_storyboard(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行分镜节点，调用 LLM 生成分镜脚本。"""
    project = getattr(node_run.canvas, 'project', None)
    if not project:
        raise RuntimeError('当前工作流画板未绑定项目，无法生成分镜')

    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    if not raw_text:
        raise RuntimeError('缺少分镜生成所需的文本内容')

    prompt_template = resolve_storyboard_template(node_run, input_payload)
    if not prompt_template:
        raise RuntimeError('未找到可用的分镜提示词模板')

    resolved_model = (input_payload.get('model') or '').strip()
    provider = _pick_provider('llm', resolved_model or (prompt_template.model_provider.model_name if prompt_template.model_provider else ''))
    if not provider and prompt_template.model_provider:
        provider = prompt_template.model_provider
    if not provider:
        provider = _pick_provider('llm', '')
    if not provider:
        raise RuntimeError('没有可用的 LLM 模型提供商，请在 ai_story 后台配置 ModelProvider')

    system_prompt = render_storyboard_system_prompt(project, prompt_template, input_payload)
    user_prompt = f'## 用户输入\n{raw_text}'
    max_tokens = _parse_int(input_payload.get('max_tokens'), 40960) or 40960
    temperature = input_payload.get('temperature', 0.8)
    top_p = input_payload.get('top_p', 1.0)

    client = create_ai_client_for_user(provider, user=project.user)
    # 分镜输出较长，给流式读取更宽的超时窗口，避免长文本响应中途被 requests 读超时打断。
    client.config['timeout'] = max(int(client.config.get('timeout') or 0), int(provider.timeout or 0), 300)

    result = {
        'id': f'chatcmpl-{uuid.uuid4().hex[:8]}',
        'model': provider.model_name,
        'metadata': {},
    }

    if hasattr(client, 'generate_stream'):
        stream_result = collect_llm_stream_text(
            client,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        generated_text = stream_result['text']
        result['metadata'].update(stream_result.get('metadata') or {})
        result['metadata']['latency_ms'] = stream_result['latency_ms']
    else:
        payload = {
            'model': provider.model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False,
        }
        headers = {
            'Authorization': f'Bearer {provider.api_key}',
            'Content-Type': 'application/json',
        }

        start_time = time.time()
        response = requests.post(
            provider.api_url,
            headers=headers,
            json=payload,
            timeout=max(int(provider.timeout or 0), 300),
        )
        latency_ms = int((time.time() - start_time) * 1000)
        if response.status_code != 200:
            raise RuntimeError(f'上游 API 请求失败: {response.status_code}')

        result = response.json()
        if 'id' not in result:
            result['id'] = f'chatcmpl-{uuid.uuid4().hex[:8]}'
        result.setdefault('model', provider.model_name)
        result.setdefault('metadata', {})
        result['metadata']['latency_ms'] = latency_ms
        generated_text = extract_assistant_text(result)

    result.setdefault('metadata', {})
    result['metadata'].update({
        'provider': _build_provider_payload(provider),
        'prompt_template_id': str(prompt_template.id),
        'prompt_template_name': prompt_template.template_set.name,
    })

    if not generated_text:
        raise RuntimeError('模型未返回可解析的分镜内容')

    parsed_storyboard = parse_storyboard_json(generated_text)
    scenes = parsed_storyboard.get('scenes', [])
    storyboards = [
        _normalize_storyboard_scene(scene, index)
        for index, scene in enumerate(scenes, start=1)
    ]
    if not storyboards:
        raise RuntimeError('分镜结果为空')

    normalized_output = {
        'text': generated_text,
        'raw_text': raw_text,
        'model': resolved_model or provider.model_name,
        'prompt_template_id': str(prompt_template.id),
        'prompt_template_name': prompt_template.template_set.name,
        'storyboards': storyboards,
    }
    return {
        'output_payload': {
            **result,
            'parsed_storyboard': parsed_storyboard,
        },
        'normalized_output': normalized_output,
    }
