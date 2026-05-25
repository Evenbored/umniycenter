from django.urls import path
from . import views

urlpatterns = [
    path("", views.CrmDashboardAPIView.as_view(), name="dashboard"),
    path("students/<int:student_id>/history/", views.student_account_history, name="student_account_history"),
]
