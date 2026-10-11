from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="display_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    hub_id = serializers.UUIDField(source="hub.id", read_only=True, allow_null=True)
    hub_name = serializers.CharField(source="hub.name", read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", "full_name",
            "phone_number", "role", "role_display", "hub_id", "hub_name", "is_active", "date_joined",
        )
        read_only_fields = fields


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["hub_id"] = str(user.hub_id) if user.hub_id else None
        token["hub_name"] = user.hub.name if user.hub else None
        token["role"] = user.role
        return token