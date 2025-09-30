from django.urls import path
from .views import (
    LoginView,
    UserManagementView,
    SheetConfigView,
    LeadQueueView,
    DispositionView,
    ResetPasswordView,
    AvailabilityView,
    AppointmentView,
)

urlpatterns = [
    # --- Auth ---
    path("login/", LoginView.as_view(), name="login"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),

    # --- Users ---
    path("users/", UserManagementView.as_view(), name="user-list-create"),
    path("users/<uuid:user_id>/", UserManagementView.as_view(), name="user-update"),

    # --- Google Sheets Config ---
    path("sheet-config/", SheetConfigView.as_view(), name="sheet-config"),

    # --- Leads ---
    path("leads/queue/", LeadQueueView.as_view(), name="lead-queue"),
    path("leads/disposition/", DispositionView.as_view(), name="lead-disposition"),

    # --- Availability ---
    path("availability/", AvailabilityView.as_view(), name="availability"),

    # --- Appointments ---
    path("appointments/", AppointmentView.as_view(), name="appointments"),
    path("appointments/<uuid:appointment_id>/", AppointmentView.as_view(), name="appointment-update"),
]
