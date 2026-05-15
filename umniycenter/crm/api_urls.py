from django.urls import path
from . import api_views

urlpatterns = [
    path("", api_views.CrmDashboardAPIView.as_view(), name="dashboard"),
    path("students/<int:student_id>/history/", api_views.student_account_history, name="student_account_history"),
]
