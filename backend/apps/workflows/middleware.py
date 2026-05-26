"""Workflow-specific gzip middleware."""

import gzip

from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin


class WorkflowGZipMiddleware(MiddlewareMixin):
    """Apply gzip compression to workflows API responses only."""

    path_prefix = '/api/v1/workflows/'
    min_length = 200

    def process_response(self, request, response):
        if not request.path.startswith(self.path_prefix):
            return response

        patch_vary_headers(response, ('Accept-Encoding',))

        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        if 'gzip' not in accept_encoding.lower():
            return response

        if response.has_header('Content-Encoding'):
            return response

        if getattr(response, 'streaming', False):
            return response

        content_type = response.get('Content-Type', '')
        if content_type.startswith('text/event-stream'):
            return response

        content = response.content
        if not content or len(content) < self.min_length:
            return response

        compressed_content = gzip.compress(content)
        if len(compressed_content) >= len(content):
            return response

        response.content = compressed_content
        response['Content-Encoding'] = 'gzip'
        response['Content-Length'] = str(len(compressed_content))
        response.headers.pop('ETag', None)
        return response
