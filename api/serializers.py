from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, SheetConfig


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "role",
            "status",
            "password",
            "last_login",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "password": {"write_only": True},  # Never expose password in responses
        }
        read_only_fields = ["id", "last_login", "created_at", "updated_at"]

    def create(self, validated_data):
        """Hash password before saving."""
        if "password" in validated_data:
            validated_data["password"] = make_password(validated_data["password"])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Hash password if it's being updated."""
        if "password" in validated_data:
            validated_data["password"] = make_password(validated_data["password"])
        return super().update(instance, validated_data)


class SheetConfigSerializer(serializers.ModelSerializer):
    """Serializer for Google Sheet configuration."""
    
    class Meta:
        model = SheetConfig
        fields = ["id", "sheet_id", "tab_name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]