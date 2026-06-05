"""显式的 Chat Completions 图片协议执行器。"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from core.ai_client.base import AIResponse, Text2ImageClient as BaseText2ImageClient
from core.ai_client.image_result_utils import (
    ensure_list,
    extract_image_items_from_content,
    localize_image_item,
    merge_extra_payload,
    normalize_result_data,
)
from core.ai_client.schemas import Text2ImageRequest


class ChatCompletionsImageExecutor(BaseText2ImageClient):
    """适配通过 chat/completions 返回图片链接的文生图接口。"""

    def generate_from_text2image_request(self, request: Text2ImageRequest) -> AIResponse:
        return self._run_request(request=request)

    def _generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        **kwargs
    ) -> AIResponse:
        request = Text2ImageRequest(
            prompt=prompt,
            negative_prompt=negative_prompt,
            reference_images=ensure_list(kwargs.get('image')),
            width=width,
            height=height,
            aspect_ratio=kwargs.get('ratio', ''),
            sample_count=kwargs.get('sample_count', 1),
            seed=kwargs.get('seed'),
            extra={
                'steps': steps,
                'response_format': kwargs.get('response_format'),
                'resolution': kwargs.get('resolution', ''),
            },
        )
        return self._run_request(
            request=request,
            api_url=kwargs.get('api_url'),
            api_key=kwargs.get('api_key') or kwargs.get('session_id'),
            model_name=kwargs.get('model'),
        )

    def _run_request(
        self,
        request: Text2ImageRequest,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> AIResponse:
        start_time = time.time()
        request_url = api_url or self.api_url
        request_key = api_key or self.api_key
        request_model = model_name or self.model_name
        timeout = int(request.extra.get('timeout') or self.config.get('timeout', 60))

        prompt_text = request.prompt.strip()
        if request.negative_prompt:
            prompt_text = f"{prompt_text}\n\n负向提示词：{request.negative_prompt.strip()}"

        content: Any
        if request.reference_images:
            content = [{'type': 'text', 'text': prompt_text}]
            for image_url in request.reference_images:
                content.append({
                    'type': 'image_url',
                    'image_url': {'url': image_url},
                })
        else:
            content = prompt_text

        payload: Dict[str, Any] = {
            'model': request_model,
            'messages': [
                {
                    'role': 'user',
                    'content': content,
                }
            ],
        }
        if request.extra.get('steps'):
            payload['steps'] = request.extra['steps']
        if request.sample_count > 1:
            payload['n'] = request.sample_count
        if request.size:
            payload['size'] = request.size
        if request.extra.get('response_format'):
            payload['response_format'] = request.extra['response_format']
        if request.extra.get('modalities'):
            payload['modalities'] = request.extra['modalities']

        merge_extra_payload(
            payload,
            request.extra,
            reserved_keys={'timeout', 'steps', 'response_format', 'modalities'},
        )

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {request_key}',
        }

        try:
            response = requests.post(
                request_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if response.status_code != 200:
                return AIResponse(
                    success=False,
                    error=f'API请求失败: {response.status_code} - {response.text}',
                )

            result = response.json()
            latency_ms = int((time.time() - start_time) * 1000)

            result_data = normalize_result_data(result.get('data'))
            if result_data:
                images_data = []
                image_urls = []
                for item in result_data:
                    if not item.get('url') and not item.get('b64_json'):
                        continue
                    localized = localize_image_item(
                        item=item,
                        width=request.width or 1024,
                        height=request.height or 1024,
                        timeout=timeout,
                    )
                    if localized.get('url'):
                        image_urls.append(localized['url'])
                    images_data.append(localized)

                if images_data:
                    return AIResponse(
                        success=True,
                        text='\n'.join(image_urls),
                        data=images_data,
                        metadata={
                            'latency_ms': latency_ms,
                            'model': request_model,
                            'request_url': request_url,
                            'input_image_count': len(request.reference_images),
                            'usage': result.get('usage', {}),
                        },
                    )

            choices = result.get('choices') or []
            if not choices:
                return AIResponse(
                    success=False,
                    error='响应格式错误: 缺少choices字段或choices为空',
                )

            message = choices[0].get('message', {})
            message_content = message.get('content', '')
            image_items = extract_image_items_from_content(message_content)
            if not image_items:
                return AIResponse(
                    success=False,
                    error='响应格式错误: 未从返回内容中解析到图片结果',
                    metadata={
                        'latency_ms': latency_ms,
                        'model': request_model,
                        'request_url': request_url,
                        'raw_content': message_content,
                    },
                )

            images_data = []
            for image_item in image_items:
                localized = localize_image_item(
                    item=image_item,
                    width=request.width or 1024,
                    height=request.height or 1024,
                    timeout=timeout,
                )
                images_data.append(localized)

            return AIResponse(
                success=True,
                text='\n'.join(item.get('url', '') for item in images_data if item.get('url')),
                data=images_data,
                metadata={
                    'latency_ms': latency_ms,
                    'model': request_model,
                    'request_url': request_url,
                    'input_image_count': len(request.reference_images),
                    'usage': result.get('usage', {}),
                },
            )
        except requests.exceptions.RequestException as exc:
            return AIResponse(success=False, error=f'网络请求错误: {str(exc)}')
        except ValueError as exc:
            return AIResponse(success=False, error=f'响应解析错误: {str(exc)}')
        except Exception as exc:
            return AIResponse(success=False, error=f'未知错误: {str(exc)}')

    def validate_config(self) -> bool:
        return bool(self.api_url and self.api_key and self.model_name)
