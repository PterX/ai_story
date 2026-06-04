from django.urls import include, path
from rest_framework import routers

from apps.mcp import views
from apps.mcp.rpc import MCPServerView, MCPSSEMessageView


router = routers.DefaultRouter()
router.register(r'', views.MCPMetaViewSet, basename='mcp-meta')


urlpatterns = [
    path('', MCPServerView.as_view()),
    path('messages/', MCPSSEMessageView.as_view()),
    path('meta/', include(router.urls)),
]
