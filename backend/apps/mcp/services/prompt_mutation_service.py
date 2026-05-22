from apps.prompts.debug_services import PromptDebugService
from apps.prompts.models import PromptDebugSession, PromptTemplate, PromptTemplateSet
from apps.prompts.serializers import PromptDebugSaveTemplateSerializer, PromptTemplateSerializer, PromptTemplateSetSerializer


class _SystemActor(object):
    is_staff = True


class _SystemRequest(object):
    def __init__(self):
        self.user = _SystemActor()


def update_prompt_template(template_id, updates):
    template = PromptTemplate.objects.select_related('template_set', 'model_provider').filter(id=template_id).first()
    if not template:
        return None

    serializer = PromptTemplateSerializer(template, data=updates, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    template.refresh_from_db()
    return PromptTemplateSerializer(template).data


def create_prompt_template_version(template_id, payload):
    template = PromptTemplate.objects.select_related('template_set', 'model_provider').filter(id=template_id).first()
    if not template:
        return None

    validation_payload = {}
    for field in ['template_content', 'variables', 'client_params', 'model_provider']:
        if field in payload:
            validation_payload[field] = payload.get(field)

    serializer = PromptTemplateSerializer(template, data=validation_payload, partial=True)
    serializer.is_valid(raise_exception=True)

    new_template = PromptTemplate.objects.create(
        template_set=template.template_set,
        stage_type=template.stage_type,
        model_provider=serializer.validated_data.get('model_provider', template.model_provider),
        template_content=serializer.validated_data.get('template_content', template.template_content),
        variables=serializer.validated_data.get('variables', template.variables),
        client_params=serializer.validated_data.get('client_params', template.client_params),
        version=template.version + 1,
        is_active=True,
    )
    template.is_active = False
    template.save(update_fields=['is_active', 'updated_at'])
    return PromptTemplateSerializer(new_template).data


def update_prompt_template_set(template_set_id, updates):
    template_set = PromptTemplateSet.objects.prefetch_related('templates__model_provider').filter(id=template_set_id).first()
    if not template_set:
        return None

    serializer = PromptTemplateSetSerializer(
        template_set,
        data=updates,
        partial=True,
        context={'request': _SystemRequest()},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    template_set.refresh_from_db()
    return PromptTemplateSetSerializer(template_set, context={'request': _SystemRequest()}).data


def set_default_prompt_template_set(template_set_id):
    template_set = PromptTemplateSet.objects.prefetch_related('templates__model_provider').filter(id=template_set_id).first()
    if not template_set:
        return None

    PromptTemplateSet.objects.filter(is_default=True).update(is_default=False)
    template_set.is_default = True
    template_set.save(update_fields=['is_default', 'updated_at'])
    return PromptTemplateSetSerializer(template_set, context={'request': _SystemRequest()}).data


def save_prompt_debug_session_to_template(session_id, payload, as_version=False):
    session = PromptDebugSession.objects.select_related('prompt_template', 'created_by').filter(id=session_id).first()
    if not session:
        return None

    serializer = PromptDebugSaveTemplateSerializer(data=payload, context={'session': session})
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data

    if as_version:
        template = PromptDebugService.create_template_version(
            session=session,
            template_content=validated['template_content'],
            variables=validated.get('variables') or {},
            client_params=validated.get('client_params') or {},
            model_provider_id=validated.get('model_provider_id'),
        )
    else:
        template = PromptDebugService.save_to_template(
            session=session,
            template_content=validated['template_content'],
            variables=validated.get('variables') or {},
            client_params=validated.get('client_params') or {},
            model_provider_id=validated.get('model_provider_id'),
        )
    return PromptTemplateSerializer(template).data
