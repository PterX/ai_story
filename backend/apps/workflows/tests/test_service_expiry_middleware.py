from datetime import date
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(
    MCP_ACCESS_TOKEN='test-token',
)
class LimitedServiceExpiryTest(APITestCase):
    def _auth(self):
        return {'HTTP_AUTHORIZATION': 'Bearer test-token'}

    def test_limited_services_are_available_on_cutoff_date(self):
        with patch('apps.mcp.rpc.timezone.localdate', return_value=date(2026, 7, 30)):
            response = self.client.get('/mcp/', **self._auth())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_limited_services_return_503_after_cutoff_date(self):
        checks = (
            ('/mcp/', 'apps.mcp.rpc.timezone.localdate'),
            ('/api/v1/agent/models/', 'apps.agent.views.timezone.localdate'),
            ('/api/v1/workflows/canvases/', 'apps.workflows.views.timezone.localdate'),
        )

        for path, patch_target in checks:
            with patch(patch_target, return_value=date(2026, 7, 31)):
                response = self.client.get(path, **self._auth())

            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()['code'], 'service_expired')
