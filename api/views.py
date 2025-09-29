from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password, check_password
from .models import User, SheetConfig
from .serializers import UserSerializer, SheetConfigSerializer
from .utils import get_qualified_lead, update_lead_disposition, verify_sheet_connection
from datetime import datetime
import uuid

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.role == 'admin'

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        try:
            user = User.objects.get(email=email)
            if check_password(password, user.password):
                user.last_login = datetime.now()
                user.save()
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'role': user.role,
                    'user_id': str(user.id),
                })
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class UserManagementView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data
        data['password'] = make_password(data.get('password'))
        data['role'] = data.get('role', 'agent')
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            data = request.data
            if 'password' in data:
                data['password'] = make_password(data['password'])
            serializer = UserSerializer(user, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

class SheetConfigView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        config = SheetConfig.objects.first()
        if config:
            serializer = SheetConfigSerializer(config)
            return Response(serializer.data)
        return Response({'error': 'No configuration found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        sheet_id = request.data.get('sheet_id')
        tab_name = request.data.get('tab_name')
        success, message = verify_sheet_connection(sheet_id, tab_name)
        if not success:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        config = SheetConfig.objects.first()
        data = {'sheet_id': sheet_id, 'tab_name': tab_name}
        if config:
            serializer = SheetConfigSerializer(config, data=data, partial=True)
        else:
            serializer = SheetConfigSerializer(data=data)
        
        if serializer.is_valid():
            serializer.save()
            return Response({'message': message}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LeadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        config = SheetConfig.objects.first()
        if not config:
            return Response({'error': 'Sheet not configured'}, status=status.HTTP_400_BAD_REQUEST)
        
        lead = get_qualified_lead(config.sheet_id, config.tab_name, request.user.id)
        if lead:
            return Response(lead)
        return Response({'message': 'Waiting patiently for a lead to come in...'}, status=status.HTTP_200_OK)

class DispositionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        config = SheetConfig.objects.first()
        if not config:
            return Response({'error': 'Sheet not configured'}, status=status.HTTP_400_BAD_REQUEST)
        
        row_index = request.data.get('row_index')
        disposition = request.data.get('disposition')
        extra_data = request.data.get('extra_data', {})
        
        try:
            update_lead_disposition(config.sheet_id, config.tab_name, row_index, disposition, request.user.id, extra_data)
            return Response({'status': 'success'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)