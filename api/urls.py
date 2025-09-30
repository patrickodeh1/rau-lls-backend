from django.urls import path
from .views import LoginView, UserManagementView, SheetConfigView, LeadView, DispositionView, ResetPasswordView, LeadQueueView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('users/', UserManagementView.as_view(), name='user-management'),
    path('users/<uuid:user_id>/', UserManagementView.as_view(), name='user-detail'),
    path('sheet-config/', SheetConfigView.as_view(), name='sheet-config'),
    path('leads/', LeadView.as_view(), name='leads'),
    path('disposition/', DispositionView.as_view(), name='disposition'),
]

urlpatterns += [
    path('users/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]

urlpatterns += [
    path('leads/next/', LeadView.as_view(), name='leads-next'),
]

urlpatterns += [
    path('leads/queue/', LeadQueueView.as_view(), name='leads-queue'),
]