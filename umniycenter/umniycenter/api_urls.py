from django.urls import path, include


from main.api.views import (
    ParticipantRequestListAPIView,
    mark_request_processed,
    create_student_from_request
)

app_name = "api"

urlpatterns = [
    path("participant-requests/", ParticipantRequestListAPIView.as_view(), name="participant_requests"),
    path("participant-requests/<int:pk>/mark-processed/", mark_request_processed, name="mark_request_processed"),
    path("participant-requests/<int:pk>/create-student/", create_student_from_request, name="create_student_from_request"),
    
    path("homework/", include('homework.api.urls')),
    path("students/", include('students.api.urls')),
    path("courses/", include('courses.api.urls')),
    path("groups/", include('groups.api.urls')),
    path("schedule/", include('schedule.api.urls')),
    path("sales/", include('sales.api.urls')),
    path("dashboard/", include('crm.api.urls')),
    path("", include('accounts.api.urls')),
    path("subscriptions/", include('subscriptions.urls')),
    path("communication/", include('communication.api.urls')),
]
