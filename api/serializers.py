from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, SheetConfig, Availability, Appointment, Lead


class UserSerializer(serializers.ModelSerializer):
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
            "password": {"write_only": True},  # never expose password
        }
        read_only_fields = ["last_login", "created_at", "updated_at"]

    def create(self, validated_data):
        if "password" in validated_data:
            validated_data["password"] = make_password(validated_data["password"])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "password" in validated_data:
            validated_data["password"] = make_password(validated_data["password"])
        return super().update(instance, validated_data)


class SheetConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SheetConfig
        fields = ["id", "sheet_id", "tab_name", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "external_id",  # e.g. Google Sheets row index or UUID
            "data",
            "locked_by",
            "locked_at",
            "status",
        ]
        read_only_fields = ["locked_by", "locked_at", "status"]


class AvailabilitySerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.name", read_only=True)

    class Meta:
        model = Availability
        fields = [
            "id",
            "agent",
            "agent_name",
            "date",
            "start_time",
            "end_time",
        ]
        extra_kwargs = {
            "agent": {"write_only": True},  # prevent exposing full agent object
        }
        read_only_fields = ["agent"]


class AppointmentSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.name", read_only=True)
    lead_data = serializers.JSONField(source="lead.data", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "owner",
            "owner_name",
            "lead",
            "lead_data",
            "date",
            "time",
            "notes",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "status", "created_at", "updated_at"]
