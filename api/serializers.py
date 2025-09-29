from rest_framework import serializers
from .models import User, SheetConfig

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'status', 'last_login', 'created_at', 'updated_at']
        read_only_fields = ['last_login', 'created_at', 'updated_at']

class SheetConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SheetConfig
        fields = ['id', 'sheet_id', 'tab_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']