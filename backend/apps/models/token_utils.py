"""Backward-compatible AI client helpers.

User-provided API keys are no longer supported. The provider's configured
credentials are always used instead.
"""

from core.ai_client.factory import create_ai_client


def create_ai_client_for_user(provider, user=None, user_id=None):
    """Create a client from the provider configuration only."""
    return create_ai_client(provider)
