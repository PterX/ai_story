from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.mcp.auth import check_mcp_auth
from apps.mcp.meta import get_mcp_module_plan, get_mcp_runtime_report
from apps.mcp.registry import list_tool_groups
from apps.mcp.serializers import MCPModuleFilterSerializer


class MCPMetaViewSet(ViewSet):
    authentication_classes = ()
    permission_classes = ()

    def _auth(self, request):
        return check_mcp_auth(request)

    def list(self, request):
        auth_error = self._auth(request)
        if auth_error is not None:
            return auth_error
        return Response(get_mcp_runtime_report())

    @action(methods=['GET'], detail=False)
    def status(self, request):
        auth_error = self._auth(request)
        if auth_error is not None:
            return auth_error
        return Response(get_mcp_runtime_report())

    @action(methods=['GET'], detail=False)
    def modules(self, request):
        auth_error = self._auth(request)
        if auth_error is not None:
            return auth_error

        serializer = MCPModuleFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        modules = get_mcp_module_plan()
        phase = validated_data.get('phase')
        status = validated_data.get('status')
        if phase is not None:
            modules = [item for item in modules if item['phase'] == phase]
        if status:
            modules = [item for item in modules if item['status'] == status]
        return Response(modules)

    @action(methods=['GET'], detail=False)
    def tools(self, request):
        auth_error = self._auth(request)
        if auth_error is not None:
            return auth_error
        return Response(list_tool_groups())

    @action(methods=['GET'], detail=False)
    def upgrade_guide(self, request):
        auth_error = self._auth(request)
        if auth_error is not None:
            return auth_error
        report = get_mcp_runtime_report()
        return Response(
            {
                'ready': report['ready'],
                'blocking_reasons': report.get('blocking_reasons', []),
                'next_steps': report.get('next_steps', []),
            }
        )

