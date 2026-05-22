from rest_framework import serializers


class MCPModuleFilterSerializer(serializers.Serializer):
    phase = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False, allow_blank=False)

