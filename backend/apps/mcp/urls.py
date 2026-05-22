from django.urls import include, path
from rest_framework import routers

from apps.mcp import views
from apps.mcp.rpc import MCPServerView


router = routers.DefaultRouter()
router.register(r'', views.MCPMetaViewSet, basename='mcp-meta')


urlpatterns = [
    path('', MCPServerView.as_view()),
    path('meta/', include(router.urls)),
]

