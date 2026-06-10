"""
主URL配置
遵循REST API最佳实践
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def superuser_admin_permission(request):
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = superuser_admin_permission

urlpatterns = [
    path('admin/', admin.site.urls),
    path('mcp/', include('apps.mcp.urls')),
    path('api/v1/projects/', include('apps.projects.urls')),
    path('api/v1/prompts/', include('apps.prompts.urls')),
    path('api/v1/models/', include('apps.models.urls')),
    path('api/v1/content/', include('apps.content.urls')),
    path('api/v1/users/', include('apps.users.urls')),
    path('api/v1/agent/', include('apps.agent.urls')),
    path('api/v1/ai/', include('apps.ai_proxy.urls')),
    path('api/v1/scripts/', include('apps.scripts.urls')),
    path('api/v1/workflows/', include('apps.workflows.urls')),
    path('api/mock/', include('apps.mock_api.urls')),
]

# 开发环境下提供媒体文件和 storage 文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STORAGE_URL, document_root=settings.STORAGE_ROOT)
