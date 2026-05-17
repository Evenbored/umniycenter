from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("dashboard-insights/", views.dashboard_insights, name="dashboard_insights"),
]
