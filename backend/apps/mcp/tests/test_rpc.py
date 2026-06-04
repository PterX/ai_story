import json
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(MCP_ACCESS_TOKEN='test-token')
class MCPRPCTestCase(APITestCase):
    def _auth(self):
        return {'HTTP_AUTHORIZATION': 'Bearer test-token'}

    def test_get_returns_json_without_sse_accept_header(self):
        response = self.client.get('/mcp/', **self._auth())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json()['status'], 'ok')

    def test_get_accepts_sse_transport(self):
        response = self.client.get(
            '/mcp/',
            HTTP_ACCEPT='text/event-stream',
            stream=True,
            **self._auth(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/event-stream'))

        stream = iter(response.streaming_content)
        first_event = next(stream).decode('utf-8')
        response.close()

        self.assertIn('event: endpoint', first_event)
        self.assertIn('/mcp/messages/?session_id=', first_event)

    def test_sse_message_endpoint_pushes_jsonrpc_response_to_stream(self):
        response = self.client.get(
            '/mcp/',
            HTTP_ACCEPT='text/event-stream',
            stream=True,
            **self._auth(),
        )
        stream = iter(response.streaming_content)
        endpoint_event = next(stream).decode('utf-8')
        endpoint = endpoint_event.split('data: ', 1)[1].strip()
        parsed_endpoint = urlparse(endpoint)
        session_id = parse_qs(parsed_endpoint.query)['session_id'][0]

        post_response = self.client.post(
            f'/mcp/messages/?session_id={session_id}',
            data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}),
            content_type='application/json',
            **self._auth(),
        )

        self.assertEqual(post_response.status_code, 202)
        message_event = next(stream).decode('utf-8')
        response.close()

        self.assertIn('data: ', message_event)
        payload = json.loads(message_event.split('data: ', 1)[1])
        self.assertEqual(payload['id'], 1)
        self.assertEqual(payload['result']['serverInfo']['name'], 'ai-story-native-mcp')

    def test_initialize_uses_client_protocol_version_when_supported(self):
        response = self.client.post(
            '/mcp/',
            data={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {'protocolVersion': '2024-11-05'},
            },
            format='json',
            **self._auth(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['protocolVersion'], '2024-11-05')
