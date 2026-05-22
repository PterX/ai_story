from django.conf import settings


BUILTIN_FREE_AGENT_MODELS = [
    {
        'id': 'builtin:opencode/big-pickle',
        'provider_id': 'opencode',
        'model_id': 'big-pickle',
        'name': 'OpenCode Free',
        'model_name': 'Big Pickle',
        'variant': '',
    },
    {
        'id': 'builtin:opencode/mimo-v2-pro-free',
        'provider_id': 'opencode',
        'model_id': 'mimo-v2-pro-free',
        'name': 'OpenCode Free',
        'model_name': 'MiMo V2 Pro Free',
        'variant': '',
    },
    {
        'id': 'builtin:opencode/mimo-v2-omni-free',
        'provider_id': 'opencode',
        'model_id': 'mimo-v2-omni-free',
        'name': 'OpenCode Free',
        'model_name': 'MiMo V2 Omni Free',
        'variant': '',
    },
    {
        'id': 'builtin:opencode/qwen3.6-plus-free',
        'provider_id': 'opencode',
        'model_id': 'qwen3.6-plus-free',
        'name': 'OpenCode Free',
        'model_name': 'Qwen3.6 Plus Free',
        'variant': '',
    },
    {
        'id': 'builtin:opencode/nemotron-3-super-free',
        'provider_id': 'opencode',
        'model_id': 'nemotron-3-super-free',
        'name': 'OpenCode Free',
        'model_name': 'Nemotron 3 Super Free',
        'variant': '',
    },
    {
        'id': 'builtin:opencode/minimax-m2.5-free',
        'provider_id': 'opencode',
        'model_id': 'minimax-m2.5-free',
        'name': 'OpenCode Free',
        'model_name': 'MiniMax M2.5 Free',
        'variant': '',
    },
]


class BuiltinAgentModelRegistry:
    @classmethod
    def _get_bool_setting(cls, key, default=False):
        value = getattr(settings, key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    @classmethod
    def show_free_models(cls):
        return cls._get_bool_setting('AGENT_SHOW_FREE_MODELS', False)

    @classmethod
    def list_models(cls):
        if not cls.show_free_models():
            return []
        return [dict(item) for item in BUILTIN_FREE_AGENT_MODELS]

    @classmethod
    def get_model(cls, provider_id):
        normalized = str(provider_id or '').strip()
        if not normalized:
            return None
        for item in cls.list_models():
            if item['id'] == normalized:
                return item
        return None

    @classmethod
    def is_valid_selection(cls, provider_id):
        return cls.get_model(provider_id) is not None
