import json
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from apps.models.models import ModelProvider
from apps.models.opencode_config import OpencodeConfigSyncService
from apps.users.models import UserPreference
from .services.builtin_models import BuiltinAgentModelRegistry
from .services.context_builder import AgentContextBuilder
from .services.gateway import AgentGateway
from .services.session_manager import AgentSessionManager


ASSISTANT_MODEL_PREFERENCE_KEY = 'assistant_model_provider_id'


def _is_supported_assistant_model(provider_id, require_opencode_support=False):
    normalized_provider_id = (provider_id or '').strip()
    if not normalized_provider_id:
        return True

    if BuiltinAgentModelRegistry.is_valid_selection(normalized_provider_id):
        return True

    try:
        provider = ModelProvider.objects.filter(
            id=normalized_provider_id,
            provider_type='llm',
            is_active=True,
        ).first()
    except (ValidationError, ValueError, TypeError):
        return False

    if not provider:
        return False

    if require_opencode_support and not OpencodeConfigSyncService.is_supported_provider(provider):
        return False
    return True


def _normalize_assistant_model_provider_id(provider_id, require_opencode_support=False):
    normalized_provider_id = (provider_id or '').strip()
    if not normalized_provider_id:
        return ''
    if _is_supported_assistant_model(
        normalized_provider_id,
        require_opencode_support=require_opencode_support,
    ):
        return normalized_provider_id
    return ''


class AgentStreamAuthMixin:
    def _authenticate_stream_user(self, request):
        token = (request.query_params.get('access_token') or '').strip()
        if not token:
            return None

        try:
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            if not user_id:
                return None
            return get_user_model().objects.filter(id=user_id).first()
        except Exception:
            return None


class AgentSessionInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        scope_key = (request.data.get('scope_key') or '').strip()
        route_name = (request.data.get('route_name') or '').strip()
        route_params = request.data.get('route_params') or {}
        ui_context = request.data.get('ui_context') or {}
        selected_model_provider_id = (request.data.get('selected_model_provider_id') or '').strip()
        if not selected_model_provider_id:
            selected_model_provider_id = self._get_persisted_model_provider_id(request.user)

        if not scope_key:
            return Response({'error': '缺少 scope_key'}, status=status.HTTP_400_BAD_REQUEST)

        if not _is_supported_assistant_model(selected_model_provider_id):
            return Response({'error': '所选助手模型不可用'}, status=status.HTTP_400_BAD_REQUEST)

        manager = AgentSessionManager()
        _, created = manager.init_session(
            user_id=request.user.id,
            scope_key=scope_key,
            route_name=route_name,
            route_params=route_params,
            ui_context=ui_context,
            selected_model_provider_id=selected_model_provider_id,
        )

        return Response({
            'scope_key': scope_key,
            'created': created,
            'selected_model_provider_id': selected_model_provider_id,
            'stream_url': f'/api/v1/agent/session/{scope_key}/stream/',
        })

    @staticmethod
    def _get_persisted_model_provider_id(user):
        preference = UserPreference.objects.filter(
            user=user,
            key=ASSISTANT_MODEL_PREFERENCE_KEY,
        ).first()
        return _normalize_assistant_model_provider_id(preference.value if preference else '')


class AgentSessionMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scope_key):
        text = (request.data.get('text') or '').strip()
        ui_context = request.data.get('ui_context') or {}
        selected_model_provider_id = (request.data.get('selected_model_provider_id') or '').strip()
        if not text:
            return Response({'error': '缺少 text'}, status=status.HTTP_400_BAD_REQUEST)

        if not _is_supported_assistant_model(selected_model_provider_id):
            return Response({'error': '所选助手模型不可用'}, status=status.HTTP_400_BAD_REQUEST)

        manager = AgentSessionManager()
        session, _ = manager.init_session(
            user_id=request.user.id,
            scope_key=scope_key,
            route_name=(request.data.get('route_name') or '').strip(),
            route_params=request.data.get('route_params') or {},
            ui_context=ui_context,
            selected_model_provider_id=selected_model_provider_id,
        )
        manager.append_message(request.user.id, scope_key, 'user', text)

        stream_token = uuid.uuid4().hex
        manager.save_stream_payload(stream_token, {
            'scope_key': scope_key,
            'user_id': request.user.id,
            'text': text,
            'ui_context': ui_context or session.get('ui_context') or {},
            'selected_model_provider_id': selected_model_provider_id or session.get('selected_model_provider_id') or '',
        })

        return Response({
            'accepted': True,
            'stream_token': stream_token,
        })


class AgentSessionStreamView(APIView, AgentStreamAuthMixin):
    permission_classes = [AllowAny]

    def get(self, request, scope_key):
        user = self._authenticate_stream_user(request)
        if not user:
            return Response({'error': '未授权访问'}, status=status.HTTP_401_UNAUTHORIZED)

        stream_token = (request.query_params.get('stream_token') or '').strip()
        if not stream_token:
            return Response({'error': '缺少 stream_token'}, status=status.HTTP_400_BAD_REQUEST)

        manager = AgentSessionManager()
        stream_payload = manager.get_stream_payload(stream_token)
        if not stream_payload:
            return Response({'error': '流式令牌无效或已过期'}, status=status.HTTP_400_BAD_REQUEST)
        if stream_payload.get('user_id') != user.id or stream_payload.get('scope_key') != scope_key:
            return Response({'error': '无权访问该流式会话'}, status=status.HTTP_403_FORBIDDEN)

        session = manager.snapshot_session(user.id, scope_key)
        if not session:
            return Response({'error': '会话不存在'}, status=status.HTTP_404_NOT_FOUND)

        context_builder = AgentContextBuilder()
        gateway = AgentGateway()

        def event_stream():
            final_message = ''
            try:
                context = context_builder.build(
                    user=user,
                    scope_key=scope_key,
                    route_name=session.get('route_name') or '',
                    route_params=session.get('route_params') or {},
                    ui_context=stream_payload.get('ui_context') or session.get('ui_context') or {},
                )

                for event in gateway.stream_response(
                    session=session,
                    user_message=stream_payload.get('text') or '',
                    context=context,
                    ui_context=stream_payload.get('ui_context') or session.get('ui_context') or {},
                    selected_model_provider_id=stream_payload.get('selected_model_provider_id') or session.get('selected_model_provider_id') or '',
                    manager=manager,
                    user_id=user.id,
                    scope_key=scope_key,
                ):
                    if event.get('type') == 'message':
                        final_message = event.get('content') or ''
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            finally:
                if final_message:
                    manager.append_message(user.id, scope_key, 'assistant', final_message)
                manager.delete_stream_payload(stream_token)

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-cache, no-transform'
        response['X-Accel-Buffering'] = 'no'
        return response


class AgentSessionUiResultView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scope_key):
        action_id = (request.data.get('action_id') or '').strip()
        intent = (request.data.get('intent') or '').strip()
        success = bool(request.data.get('success'))
        result = request.data.get('result') or ''

        manager = AgentSessionManager()
        manager.append_message(
            request.user.id,
            scope_key,
            'tool',
            result or f'{intent or action_id} 已执行',
            extra={
                'action_id': action_id,
                'intent': intent,
                'success': success,
            }
        )
        return Response({'accepted': True})


class AgentSessionAbortView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scope_key):
        manager = AgentSessionManager()
        session = manager.snapshot_session(request.user.id, scope_key)
        remote_session_id = (session or {}).get('agent_session_id')
        if remote_session_id:
            gateway = AgentGateway()
            try:
                gateway.abort_session(remote_session_id)
            except Exception:
                pass
        return Response({'accepted': True})


class AgentSessionClearView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scope_key):
        manager = AgentSessionManager()
        session = manager.snapshot_session(request.user.id, scope_key)
        remote_session_id = (session or {}).get('agent_session_id')
        if remote_session_id:
            gateway = AgentGateway()
            try:
                gateway.abort_session(remote_session_id)
            except Exception:
                pass

        manager.clear_session(request.user.id, scope_key)
        return Response({'accepted': True})


class AgentModelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        gateway = AgentGateway()
        runtime_provider_map = gateway.fetch_runtime_provider_map_safe()
        queryset = ModelProvider.objects.filter(
            provider_type='llm',
            is_active=True,
        ).order_by('-priority', '-created_at')
        queryset = [item for item in queryset if OpencodeConfigSyncService.is_supported_provider(item)]

        builtin_models = []
        for item in BuiltinAgentModelRegistry.list_models():
            runtime_status = gateway.get_runtime_model_status(
                item['provider_id'],
                item['model_id'],
                provider_map=runtime_provider_map,
            )
            builtin_models.append({
                **item,
                **runtime_status,
            })

        selected_model_provider_id = AgentSessionInitView._get_persisted_model_provider_id(request.user)
        return Response({
            'count': len(queryset) + len(builtin_models),
            'selected_model_provider_id': selected_model_provider_id,
            'results': [
                {
                    'id': str(item.id),
                    'name': item.name,
                    'model_name': item.model_name,
                    'api_url': item.api_url,
                    **gateway.get_selection_runtime_status(
                        str(item.id),
                        provider_map=runtime_provider_map,
                    ),
                }
                for item in queryset
            ] + builtin_models,
        })

    def post(self, request):
        selected_model_provider_id = (request.data.get('selected_model_provider_id') or '').strip()
        if not selected_model_provider_id:
            return Response({'error': '缺少 selected_model_provider_id'}, status=status.HTTP_400_BAD_REQUEST)

        if not _is_supported_assistant_model(selected_model_provider_id, require_opencode_support=True):
            return Response({'error': '所选助手模型不可用'}, status=status.HTTP_400_BAD_REQUEST)

        gateway = AgentGateway()
        runtime_status = gateway.get_selection_runtime_status(selected_model_provider_id)
        if not runtime_status['runtime_available']:
            if runtime_status['runtime_status'] == 'restart_required':
                return Response({'error': '所选助手模型尚未被 opencode serve 加载，请重启 opencode serve 后重试。'}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': '暂时无法确认所选助手模型的运行时状态，请稍后重试。'}, status=status.HTTP_400_BAD_REQUEST)

        UserPreference.objects.update_or_create(
            user=request.user,
            key=ASSISTANT_MODEL_PREFERENCE_KEY,
            defaults={'value': selected_model_provider_id},
        )
        return Response({'accepted': True, 'selected_model_provider_id': selected_model_provider_id})
