import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core.ai_client.openai_client import OpenAIClient


class OpenAIClientTestCase(SimpleTestCase):
    @patch('core.ai_client.openai_client.requests.post')
    def test_generate_stream_handles_split_utf8_bytes(self, mock_post):
        cat_text = '\u732b'
        first_event = (
            f'data: {json.dumps({"choices": [{"delta": {"content": cat_text}, "finish_reason": None}]}, ensure_ascii=False)}\n'
        ).encode('utf-8')
        second_event = (
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n'
        ).encode('utf-8')

        split_index = first_event.index(cat_text.encode('utf-8')) + 2
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [
            first_event[:split_index],
            first_event[split_index:],
            second_event,
        ]
        mock_post.return_value = mock_response

        client = OpenAIClient(
            api_url='https://example.com/v1/chat/completions',
            api_key='test-key',
            model_name='gpt-test',
        )

        chunks = list(client.generate_stream(prompt='hello'))

        self.assertEqual(chunks[0]['type'], 'token')
        self.assertEqual(chunks[0]['content'], cat_text)
        self.assertEqual(chunks[0]['full_text'], cat_text)
        self.assertEqual(chunks[1]['type'], 'done')
        self.assertEqual(chunks[1]['full_text'], cat_text)
