from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils.timezone import now
from datetime import datetime
import uuid
import string
import random
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    User,
    SheetConfig,
    Availability,
    Appointment,
    Lead,
)
from .serializers import (
    UserSerializer,
    SheetConfigSerializer,
    AvailabilitySerializer,
    AppointmentSerializer,
)
from .utils import (
    verify_sheet_connection,
    add_appointment_to_sheet,
    update_appointment_in_sheet,
    update_lead_disposition,
)
from api.permissions import IsAdmin


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == "admin"


# ----------------------
# Auth
# ----------------------
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        try:
            user = User.objects.get(email=email)
            if check_password(password, user.password):
                user.last_login = datetime.now()
                user.save()
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                        "role": user.role,
                        "user_id": str(user.id),
                    }
                )
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


# ----------------------
# User Management
# ----------------------
class UserManagementView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        if "generate_password" in request.data:
            temp_password = "".join(
                random.choices(string.ascii_letters + string.digits, k=12)
            )
            data["password"] = temp_password
        data["role"] = data.get("role", "agent")
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()
            return Response(UserSerializer(updated_user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------
# Google Sheet Config
# ----------------------
class SheetConfigView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        config = SheetConfig.objects.first()
        if config:
            serializer = SheetConfigSerializer(config)
            return Response(serializer.data)
        return Response(
            {"error": "No configuration found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    def post(self, request):
        sheet_id = request.data.get("sheet_id")
        tab_name = request.data.get("tab_name")
        if not sheet_id or not tab_name:
            return Response(
                {"error": "sheet_id and tab_name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success, message = verify_sheet_connection(sheet_id, tab_name)
        if not success:
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        config = SheetConfig.objects.first()
        data = {"sheet_id": sheet_id, "tab_name": tab_name}
        if config:
            serializer = SheetConfigSerializer(config, data=data, partial=True)
        else:
            serializer = SheetConfigSerializer(data=data)

        if serializer.is_valid():
            config = serializer.save()
            return Response(
                {"id": config.id, "sheet_id": sheet_id, "tab_name": tab_name},
                status=status.HTTP_200_OK if config.pk else status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------
# Lead Queue
# ----------------------
class LeadQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Fetch next available lead and lock it for the agent."""
        with transaction.atomic():
            lead = (
                Lead.objects.select_for_update(skip_locked=True)
                .filter(locked_by__isnull=True, status="NEW")
                .first()
            )

            if not lead:
                return Response(
                    {"message": "No available leads"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            lead.locked_by = request.user
            lead.locked_at = now()
            lead.save()

            return Response({"lead": lead.data, "lead_id": lead.id})


# ----------------------
# Lead Disposition
# ----------------------
class DispositionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        config = SheetConfig.objects.first()
        if not config:
            return Response(
                {"error": "Sheet not configured"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        row_index = request.data.get("row_index")
        disposition = request.data.get("disposition")
        extra_data = request.data.get("extra_data", {})

        try:
            update_lead_disposition(
                config.sheet_id,
                config.tab_name,
                row_index,
                disposition,
                request.user.id,
                extra_data,
            )
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ----------------------
# Reset Password
# ----------------------
class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
            token = str(uuid.uuid4())  # TODO: Store securely
            # send_mail('Password Reset', f'Use this token: {token}', settings.EMAIL_HOST_USER, [email])
            return Response(
                {"message": "Reset token sent (email not configured yet)"},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


# ----------------------
# Availability Management (Admin/Agent)
# ----------------------
class AvailabilityView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        slots = Availability.objects.all()
        serializer = AvailabilitySerializer(slots, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AvailabilitySerializer(data=request.data)
        if serializer.is_valid():
            # ✅ Assign agent automatically if not provided
            agent = request.data.get("agent") or request.user
            serializer.save(agent=agent)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------
# Appointment Management
# ----------------------
class AppointmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List logged-in user's appointments."""
        qs = Appointment.objects.filter(owner=request.user).order_by("-created_at")
        return Response(AppointmentSerializer(qs, many=True).data)

    def post(self, request):
        """Book a new appointment & sync with Google Sheets."""
        serializer = AppointmentSerializer(data=request.data)
        if serializer.is_valid():
            appointment = serializer.save(owner=request.user)

            # ✅ Sync with Google Sheets
            config = SheetConfig.objects.first()
            if config:
                try:
                    add_appointment_to_sheet(config.sheet_id, config.tab_name, appointment)
                except Exception as e:
                    return Response(
                        {
                            "appointment": AppointmentSerializer(appointment).data,
                            "warning": f"Saved locally but Sheets sync failed: {str(e)}",
                        },
                        status=status.HTTP_201_CREATED,
                    )

            return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, appointment_id):
        """Update (reschedule or cancel) appointment & sync with Google Sheets."""
        try:
            appointment = Appointment.objects.get(id=appointment_id, owner=request.user)
        except Appointment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AppointmentSerializer(appointment, data=request.data, partial=True)
        if serializer.is_valid():
            appointment = serializer.save()

            # ✅ Sync with Google Sheets
            config = SheetConfig.objects.first()
            if config:
                try:
                    update_appointment_in_sheet(config.sheet_id, config.tab_name, appointment)
                except Exception as e:
                    return Response(
                        {
                            "appointment": AppointmentSerializer(appointment).data,
                            "warning": f"Updated locally but Sheets sync failed: {str(e)}",
                        }
                    )

            return Response(AppointmentSerializer(appointment).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
