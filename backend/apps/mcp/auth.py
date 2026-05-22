from django.conf import settings
from django.http import JsonResponse


def get_mcp_access_token():
    return (
        getattr(settings, 'MCP_ACCESS_TOKEN', '')
        or getattr(settings, 'AGENT_SERVER_PASSWORD', '')
        or ''
    ).strip()


def check_mcp_auth(request):
    expected_token = get_mcp_access_token()
    if not expected_token:
        return JsonResponse({'detail': 'MCP access token is not configured'}, status=503)

    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '', 1).strip()
    if token != expected_token:
        return JsonResponse({'detail': 'Unauthorized'}, status=401)
    return None

