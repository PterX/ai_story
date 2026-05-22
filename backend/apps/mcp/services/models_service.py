from django.db.models import Q

from apps.models.models import ModelProvider, ModelUsageLog
from apps.models.serializers import ModelProviderListSerializer, ModelUsageLogSerializer

from apps.mcp.utils.presenters import mask_secret


def list_model_providers(*, provider_type='', is_active=None, limit=20):
    queryset = ModelProvider.objects.all().prefetch_related('usage_logs').order_by('-priority', '-created_at')
    if provider_type:
        queryset = queryset.filter(provider_type=provider_type)
    if is_active is not None:
        queryset = queryset.filter(is_active=bool(is_active))
    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': ModelProviderListSerializer(items, many=True).data,
    }


def get_model_provider_detail(provider_id):
    provider = ModelProvider.objects.filter(id=provider_id).prefetch_related('usage_logs').first()
    if not provider:
        return None
    return {
        'id': str(provider.id),
        'name': provider.name,
        'provider_type': provider.provider_type,
        'provider_type_display': provider.get_provider_type_display(),
        'api_url': provider.api_url,
        'api_key_masked': mask_secret(provider.api_key),
        'model_name': provider.model_name,
        'executor_class': provider.executor_class,
        'max_tokens': provider.max_tokens,
        'temperature': provider.temperature,
        'top_p': provider.top_p,
        'timeout': provider.timeout,
        'is_active': provider.is_active,
        'priority': provider.priority,
        'rate_limit_rpm': provider.rate_limit_rpm,
        'rate_limit_rpd': provider.rate_limit_rpd,
        'extra_config': provider.extra_config,
        'total_usage_count': provider.usage_logs.count(),
        'success_count': provider.usage_logs.filter(status='success').count(),
        'failed_count': provider.usage_logs.filter(status='failed').count(),
        'created_at': provider.created_at.isoformat() if provider.created_at else None,
        'updated_at': provider.updated_at.isoformat() if provider.updated_at else None,
    }


def list_model_usage_logs(*, project_id='', stage_type='', status='', limit=20):
    queryset = ModelUsageLog.objects.all().select_related('model_provider').order_by('-created_at')
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    if stage_type:
        queryset = queryset.filter(stage_type=stage_type)
    if status:
        queryset = queryset.filter(status=status)
    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': ModelUsageLogSerializer(items, many=True).data,
    }

