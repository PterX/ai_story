import json

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.mcp.auth import check_mcp_auth
from apps.mcp.errors import MCPToolError
from apps.mcp.registry import list_tools
from apps.mcp.tools import call_tool
from apps.mcp.utils.presenters import tool_text_payload


@method_decorator(csrf_exempt, name='dispatch')
class MCPServerView(View):
    protocol_version = '2026-03-23'
    server_name = 'ai-story-native-mcp'
    server_version = '0.1.0'

    def _jsonrpc_result(self, request_id, result):
        return {'jsonrpc': '2.0', 'id': request_id, 'result': result}

    def _jsonrpc_error(self, request_id, code, message, data=None):
        payload = {
            'jsonrpc': '2.0',
            'id': request_id,
            'error': {'code': code, 'message': message},
        }
        if data is not None:
            payload['error']['data'] = data
        return payload

    def _initialize_result(self):
        return {
            'protocolVersion': self.protocol_version,
            'capabilities': {
                'tools': {'listChanged': False},
            },
            'serverInfo': {
                'name': self.server_name,
                'version': self.server_version,
            },
            'instructions': 'AI Story 原生 MCP 服务。当前提供项目、提示词、变量、模型与日志的首批只读工具。',
        }

    def get(self, request, *args, **kwargs):
        auth_error = check_mcp_auth(request)
        if auth_error is not None:
            return auth_error
        return JsonResponse(
            {
                'name': self.server_name,
                'version': self.server_version,
                'protocolVersion': self.protocol_version,
                'status': 'ok',
                'methods': ['initialize', 'ping', 'tools/list', 'tools/call'],
                'tools_count': len(list_tools()),
            },
            json_dumps_params={'ensure_ascii': False},
        )

    def post(self, request, *args, **kwargs):
        auth_error = check_mcp_auth(request)
        if auth_error is not None:
            return auth_error

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            return JsonResponse(
                self._jsonrpc_error(None, -32700, 'Parse error'),
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )

        response = self._handle_request(payload)
        if response is None:
            return HttpResponse(status=202)
        status_code = 200 if 'result' in response else 400
        return JsonResponse(response, status=status_code, json_dumps_params={'ensure_ascii': False})

    def _handle_request(self, payload):
        if not isinstance(payload, dict):
            return self._jsonrpc_error(None, -32600, 'Invalid Request')

        request_id = payload.get('id')
        method = payload.get('method')
        params = payload.get('params') or {}
        if not method:
            return self._jsonrpc_error(request_id, -32600, 'Invalid Request')

        if method == 'notifications/initialized':
            return None
        if method == 'initialize':
            return self._jsonrpc_result(request_id, self._initialize_result())
        if method == 'ping':
            return self._jsonrpc_result(request_id, {})
        if method == 'tools/list':
            return self._jsonrpc_result(request_id, {'tools': list_tools()})
        if method == 'tools/call':
            tool_name = params.get('name')
            arguments = params.get('arguments') or {}
            if not tool_name:
                return self._jsonrpc_error(request_id, -32602, 'Invalid params', {'reason': '缺少工具名称'})
            try:
                tool_result = call_tool(tool_name, arguments)
            except MCPToolError as exc:
                return self._jsonrpc_result(request_id, tool_text_payload({'error': str(exc)}, is_error=True))
            except Exception as exc:
                return self._jsonrpc_result(request_id, tool_text_payload({'error': str(exc)}, is_error=True))
            return self._jsonrpc_result(request_id, tool_text_payload(tool_result))

        return self._jsonrpc_error(request_id, -32601, 'Method not found', {'method': method})

