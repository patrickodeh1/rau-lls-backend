from django.urls import path
from .views import (
    LoginView,
    UserManagementView,
    SheetConfigView,
    LeadQueueView,
    DispositionView,
    ResetPasswordView,
)

urlpatterns = [
    # --- Auth ---
    path("login/", LoginView.as_view(), name="login"),
    
    # --- User Management (Admin) ---
    path("users/", UserManagementView.as_view(), name="user-list-create"),
    path("users/<uuid:user_id>/", UserManagementView.as_view(), name="user-detail"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    
    # --- Google Sheets Config (Admin) ---
    path("sheet-config/", SheetConfigView.as_view(), name="sheet-config"),
    
    # --- Lead Processing (Agent) ---
    path("leads/next/", LeadQueueView.as_view(), name="lead-next"),
    path("leads/disposition/", DispositionView.as_view(), name="lead-disposition"),
]