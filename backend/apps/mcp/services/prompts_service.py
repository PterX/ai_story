from django.db.models import Q
from jinja2 import Template

from apps.prompts.models import GlobalVariable, PromptTemplate, PromptTemplateSet
from apps.prompts.serializers import (
    GlobalVariableListSerializer,
    PromptTemplateListSerializer,
    PromptTemplateSerializer,
    PromptTemplateSetListSerializer,
    PromptTemplateSetSerializer,
)


def list_prompt_template_sets(*, query='', limit=20):
    queryset = PromptTemplateSet.objects.all().select_related('created_by').prefetch_related('templates').order_by('-created_at')
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': PromptTemplateSetListSerializer(items, many=True).data,
    }


def get_prompt_template_set_detail(template_set_id):
    item = PromptTemplateSet.objects.filter(id=template_set_id).select_related('created_by').prefetch_related('templates__model_provider').first()
    if not item:
        return None
    return PromptTemplateSetSerializer(item).data


def list_prompt_templates(*, template_set_id='', stage_type='', limit=20):
    queryset = PromptTemplate.objects.all().select_related('template_set', 'model_provider').order_by('-updated_at')
    if template_set_id:
        queryset = queryset.filter(template_set_id=template_set_id)
    if stage_type:
        queryset = queryset.filter(stage_type=stage_type)
    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': PromptTemplateListSerializer(items, many=True).data,
    }


def get_prompt_template_detail(template_id):
    item = PromptTemplate.objects.filter(id=template_id).select_related('template_set', 'model_provider').first()
    if not item:
        return None
    return PromptTemplateSerializer(item).data


def preview_prompt_template(template_id, variables=None):
    item = PromptTemplate.objects.filter(id=template_id).first()
    if not item:
        return None
    variables = variables or {}
    rendered = Template(item.template_content).render(**variables)
    return {
        'template_id': str(item.id),
        'stage_type': item.stage_type,
        'variables_used': variables,
        'rendered_content': rendered,
    }


def list_global_variables(*, query='', group='', scope='', limit=20):
    queryset = GlobalVariable.objects.all().select_related('created_by').order_by('group', 'key')
    if query:
        queryset = queryset.filter(Q(key__icontains=query) | Q(description__icontains=query) | Q(group__icontains=query))
    if group:
        queryset = queryset.filter(group=group)
    if scope:
        queryset = queryset.filter(scope=scope)
    items = list(queryset[:limit])
    return {
        'count': len(items),
        'results': GlobalVariableListSerializer(items, many=True).data,
    }

