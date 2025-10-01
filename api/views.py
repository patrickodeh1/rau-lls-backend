from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from django.utils.timezone import now
from datetime import datetime
import string
import random

from .models import User, SheetConfig
from .serializers import UserSerializer, SheetConfigSerializer
from .utils import (
    verify_sheet_connection,
    fetch_qualified_leads,
    lock_lead,
    update_lead_disposition,
)


# ----------------------
# Custom Permission
# ----------------------
class IsAdmin(permissions.BasePermission):
    """Only allow admin users."""
    def has_permission(self, request, view):
        return (
            request.user 
            and request.user.is_authenticated 
            and request.user.role == "admin"
        )


# ----------------------
# Auth
# ----------------------
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Explicitly bypass authentication

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        
        if not email or not password:
            return Response(
                {"error": "Email and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            user = User.objects.get(email=email)
            
            # Check if user is active
            if user.status != "active":
                return Response(
                    {"error": "Account is inactive"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            
            if check_password(password, user.password):
                # Update last login
                user.last_login = now()
                user.save()
                
                # Generate tokens
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "role": user.role,
                    "user_id": str(user.id),
                    "name": user.name,
                })
            
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


# ----------------------
# User Management (Admin Only)
# ----------------------
class UserManagementView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request, user_id=None):
        """Get all users or a specific user."""
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                serializer = UserSerializer(user)
                return Response(serializer.data)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get all users, exclude superusers
        users = User.objects.filter(is_superuser=False).order_by("-created_at")
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new agent."""
        data = request.data.copy()
        
        # Generate password if not provided
        if not data.get("password"):
            temp_password = "".join(
                random.choices(string.ascii_letters + string.digits, k=12)
            )
            data["password"] = temp_password
        
        # Force role to agent for safety
        data["role"] = data.get("role", "agent")
        data["status"] = data.get("status", "active")
        
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            response_data = UserSerializer(user).data
            # Include temp password in response if it was generated
            if not request.data.get("password"):
                response_data["temp_password"] = temp_password
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, user_id):
        """Update an existing user."""
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()
            return Response(UserSerializer(updated_user).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        """Deactivate a user (soft delete)."""
        try:
            user = User.objects.get(id=user_id)
            user.status = "inactive"
            user.save()
            return Response({"message": "User deactivated successfully"})
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )


# ----------------------
# Password Reset
# ----------------------
class ResetPasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        """Admin can reset any user's password."""
        user_id = request.data.get("user_id")
        new_password = request.data.get("new_password")
        
        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            user = User.objects.get(id=user_id)
            
            # Generate password if not provided
            if not new_password:
                new_password = "".join(
                    random.choices(string.ascii_letters + string.digits, k=12)
                )
            
            user.set_password(new_password)
            user.save()
            
            return Response({
                "message": "Password reset successfully",
                "temp_password": new_password
            })
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


# ----------------------
# Google Sheet Config (Admin Only)
# ----------------------
class SheetConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        """Get current sheet configuration."""
        config = SheetConfig.objects.first()
        if config:
            serializer = SheetConfigSerializer(config)
            return Response(serializer.data)
        
        return Response(
            {"message": "No configuration found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    def post(self, request):
        """Create or update sheet configuration."""
        sheet_id = request.data.get("sheet_id")
        tab_name = request.data.get("tab_name")
        
        if not sheet_id or not tab_name:
            return Response(
                {"error": "sheet_id and tab_name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify connection before saving
        success, message = verify_sheet_connection(sheet_id, tab_name)
        if not success:
            return Response(
                {"error": message}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update or create config
        config = SheetConfig.objects.first()
        data = {"sheet_id": sheet_id, "tab_name": tab_name}
        
        if config:
            serializer = SheetConfigSerializer(config, data=data, partial=True)
        else:
            serializer = SheetConfigSerializer(data=data)

        if serializer.is_valid():
            config = serializer.save()
            return Response({
                "message": "Configuration saved successfully",
                "sheet_id": config.sheet_id,
                "tab_name": config.tab_name,
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------
# Lead Queue (Agent Access)
# ----------------------
class LeadQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Fetch next available qualified lead and lock it for the agent.
        Returns lead data from Google Sheets.
        """
        config = SheetConfig.objects.first()
        if not config:
            return Response(
                {"error": "Google Sheet not configured. Please contact admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            # Fetch all qualified leads
            qualified_leads = fetch_qualified_leads(config.sheet_id, config.tab_name)
            
            if not qualified_leads:
                return Response(
                    {"message": "No available leads"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            # Get first qualified lead
            lead = qualified_leads[0]
            row_index = lead["row_index"]
            
            # Lock the lead for this agent
            lock_lead(config.sheet_id, config.tab_name, row_index, request.user.id)
            
            return Response({
                "lead": lead,
                "queue_count": len(qualified_leads)
            })
        
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch leads: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------
# Lead Disposition (Agent Access)
# ----------------------
class DispositionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Update lead disposition in Google Sheets.
        Handles: NA, NI, DNC, CB, BOOK
        """
        config = SheetConfig.objects.first()
        if not config:
            return Response(
                {"error": "Google Sheet not configured"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        row_index = request.data.get("row_index")
        disposition = request.data.get("disposition")
        extra_data = request.data.get("extra_data", {})

        if not row_index or not disposition:
            return Response(
                {"error": "row_index and disposition are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate disposition
        valid_dispositions = ["NA", "NI", "DNC", "CB", "BOOK"]
        if disposition not in valid_dispositions:
            return Response(
                {"error": f"Invalid disposition. Must be one of: {', '.join(valid_dispositions)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate extra data for CB and BOOK
        if disposition == "CB":
            if not extra_data.get("CB_Date") or not extra_data.get("CB_Time"):
                return Response(
                    {"error": "CB_Date and CB_Time are required for Call Back disposition"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        if disposition == "BOOK":
            if not extra_data.get("Appointment_Date") or not extra_data.get("Appointment_Time"):
                return Response(
                    {"error": "Appointment_Date and Appointment_Time are required for Book disposition"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            update_lead_disposition(
                config.sheet_id,
                config.tab_name,
                row_index,
                disposition,
                request.user.id,
                extra_data,
            )
            
            response_data = {
                "status": "success",
                "message": "Disposition updated successfully"
            }
            
            # Add celebration flag for bookings
            if disposition == "BOOK":
                response_data["celebration"] = True
            
            return Response(response_data)
        
        except Exception as e:
            return Response(
                {"error": f"Failed to update disposition: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )