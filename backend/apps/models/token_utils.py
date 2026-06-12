"""
用户 API Token 工具函数
职责: 统一获取用户 token 并创建 AI 客户端
"""

import logging
from typing import Optional

from core.ai_client.base import BaseAIClient

logger = logging.getLogger(__name__)


def get_user_api_key(user) -> Optional[str]:
    """
    获取用户的 API Token

    Args:
        user: Django User 实例

    Returns:
        Optional[str]: 用户的 API Token，未配置时返回 None
    """
    if user is None:
        return None
    try:
        token_obj = getattr(user, 'api_token', None)
        if token_obj and token_obj.api_token:
            return token_obj.api_token
    except Exception:
        pass
    return None


def get_user_api_key_by_id(user_id) -> Optional[str]:
    """
    通过 user_id 获取用户的 API Token（避免 N+1 查询）

    Args:
        user_id: 用户 ID

    Returns:
        Optional[str]: 用户的 API Token，未配置时返回 None
    """
    if user_id is None:
        return None
    from apps.models.models import UserApiToken
    try:
        token_obj = UserApiToken.objects.filter(user_id=user_id).first()
        if token_obj and token_obj.api_token:
            return token_obj.api_token
    except Exception:
        pass
    return None


def validate_user_api_key(user=None, user_id=None) -> str:
    """
    验证并获取用户的 API Token，非超级用户必须配置自己的 Token

    Args:
        user: Django User 实例（优先使用）
        user_id: 用户 ID（user 为 None 时使用）

    Returns:
        str: 用户的 API Token

    Raises:
        ValueError: 非超级用户未配置 API Token
    """
    user_api_key = None
    actual_user = user

    if user is not None:
        user_api_key = get_user_api_key(user)
    elif user_id is not None:
        user_api_key = get_user_api_key_by_id(user_id)
        # 如果只有 user_id，获取 user 对象用于判断是否是超级用户
        if user_api_key is None:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                actual_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

    # 判断是否是超级用户
    is_superuser = False
    if actual_user is not None:
        is_superuser = actual_user.is_superuser

    # 非超级用户必须配置自己的 API Token
    if not is_superuser and user_api_key is None:
        raise ValueError("必须配置自己的 API Token 才能使用 AI 功能")

    return user_api_key


def create_ai_client_for_user(provider, user=None, user_id=None) -> BaseAIClient:
    """
    为用户创建 AI 客户端，自动使用用户自定义 API Token

    Args:
        provider: ModelProvider 实例
        user: Django User 实例（优先使用）
        user_id: 用户 ID（user 为 None 时使用）

    Returns:
        BaseAIClient: 客户端实例

    Raises:
        ValueError: 非超级用户未配置 API Token
    """
    from core.ai_client.factory import create_ai_client

    user_api_key = validate_user_api_key(user=user, user_id=user_id)
    return create_ai_client(provider, user_api_key=user_api_key)
