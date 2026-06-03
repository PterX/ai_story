"""提示词模板解析与渲染工具函数。"""

from typing import Any, Dict, Optional

from jinja2 import Template, TemplateError

from apps.projects.asset_context import build_project_asset_context
from apps.prompts.models import PromptTemplate, PromptTemplateSet

from ..models import WorkflowNodeRun


# ---------------------------------------------------------------------------
# Storyboard template helpers
# ---------------------------------------------------------------------------

def get_default_storyboard_template() -> Optional[PromptTemplate]:
    """获取默认的分镜提示词模板。"""
    template_set = PromptTemplateSet.objects.filter(is_default=True).first()
    if not template_set:
        return None
    return (
        PromptTemplate.objects
        .select_related('model_provider', 'template_set')
        .filter(template_set=template_set, stage_type='storyboard', is_active=True)
        .first()
    )


def resolve_storyboard_template(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Optional[PromptTemplate]:
    """根据输入参数解析分镜提示词模板，优先使用指定模板 ID，其次使用项目绑定模板，最后使用默认模板。"""
    template_id = input_payload.get('prompt_template_id') or input_payload.get('promptTemplateId')
    queryset = PromptTemplate.objects.select_related('model_provider', 'template_set').filter(
        stage_type='storyboard',
        is_active=True,
    )

    if template_id:
        template = queryset.filter(id=template_id).first()
        if template:
            return template

    project = getattr(node_run.canvas, 'project', None)
    template_set = getattr(project, 'prompt_template_set', None) if project else None
    if template_set:
        template = queryset.filter(template_set=template_set).first()
        if template:
            return template

    return get_default_storyboard_template()


def build_storyboard_template_vars(project, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """构建分镜模板渲染所需的变量字典。"""
    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    global_vars = build_project_asset_context(project)

    return {
        **global_vars,
        'project': {
            'name': project.name,
            'description': project.description,
            'original_topic': project.original_topic,
        },
        'raw_text': raw_text,
        'original_text': raw_text,
        'text': raw_text,
        'human_text': input_payload.get('human_text') or '',
        'instruction': input_payload.get('instruction') or '',
    }


def render_storyboard_system_prompt(project, template: PromptTemplate, input_payload: Dict[str, Any]) -> str:
    """渲染分镜系统提示词。"""
    system_prompt_override = str(input_payload.get('system_prompt') or input_payload.get('systemPrompt') or '').strip()
    if system_prompt_override:
        return system_prompt_override
    try:
        return Template(template.template_content).render(**build_storyboard_template_vars(project, input_payload))
    except TemplateError as exc:
        raise RuntimeError(f'分镜提示词模板渲染失败: {exc}') from exc


# ---------------------------------------------------------------------------
# Asset extraction template helpers
# ---------------------------------------------------------------------------

def get_default_asset_extraction_template() -> Optional[PromptTemplate]:
    """获取默认的资产抽取提示词模板。"""
    template_set = PromptTemplateSet.objects.filter(is_default=True).first()
    if not template_set:
        return None
    return (
        PromptTemplate.objects
        .select_related('model_provider', 'template_set')
        .filter(template_set=template_set, stage_type='asset_extraction', is_active=True)
        .first()
    )


def resolve_asset_extraction_template(node_run: WorkflowNodeRun, input_payload: Dict[str, Any]) -> Optional[PromptTemplate]:
    """根据输入参数解析资产抽取提示词模板。"""
    template_id = input_payload.get('prompt_template_id') or input_payload.get('promptTemplateId')
    queryset = PromptTemplate.objects.select_related('model_provider', 'template_set').filter(
        stage_type='asset_extraction',
        is_active=True,
    )

    if template_id:
        template = queryset.filter(id=template_id).first()
        if template:
            return template

    project = getattr(node_run.canvas, 'project', None)
    template_set = getattr(project, 'prompt_template_set', None) if project else None
    if template_set:
        template = queryset.filter(template_set=template_set).first()
        if template:
            return template

    return get_default_asset_extraction_template()


def build_asset_extraction_template_vars(project, input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """构建资产抽取模板渲染所需的变量字典。"""
    raw_text = (
        input_payload.get('raw_text')
        or input_payload.get('source_text')
        or input_payload.get('original_text')
        or input_payload.get('text')
        or ''
    ).strip()
    global_vars = build_project_asset_context(project)

    return {
        **global_vars,
        'project': {
            'name': project.name,
            'description': project.description,
            'original_topic': project.original_topic,
        },
        'raw_text': raw_text,
        'source_text': raw_text,
        'original_text': raw_text,
        'text': raw_text,
        'human_text': input_payload.get('human_text') or '',
    }


def render_asset_extraction_system_prompt(project, template: PromptTemplate, input_payload: Dict[str, Any]) -> str:
    """渲染资产抽取系统提示词。"""
    system_prompt_override = str(input_payload.get('system_prompt') or input_payload.get('systemPrompt') or '').strip()
    if system_prompt_override:
        return system_prompt_override
    try:
        return Template(template.template_content).render(**build_asset_extraction_template_vars(project, input_payload))
    except TemplateError as exc:
        raise RuntimeError(f'资产抽取提示词模板渲染失败: {exc}') from exc
