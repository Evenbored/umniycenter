from django.urls import path, include

from courses.api_views import CourseListAPIView, create_course, update_course, delete_course
from groups.api_views import GroupsCountAPIView, MyGroupsAPIView, update_group, create_group
from homework.api_views import HomeworkListAPIView, MyHomeworkAPIView
from main.api_views import (
    ParticipantRequestListAPIView,
    mark_request_processed,
    create_student_from_request
)

app_name = "api"

urlpatterns = [
    path("participant-requests/", ParticipantRequestListAPIView.as_view(), name="participant_requests"),
    path("participant-requests/<int:pk>/mark-processed/", mark_request_processed, name="mark_request_processed"),
    path("participant-requests/<int:pk>/create-student/", create_student_from_request, name="create_student_from_request"),
    
    path("homework/", include('homework.api_urls')),
    path("students/", include('students.api_urls')),
    path("courses/", include('courses.api_urls')),
    path("groups/", include('groups.api_urls')),
    path("schedule/", include('schedule.api_urls')),
    path("dashboard/", include('crm.api_urls')),
    path("", include('accounts.api_urls')),
    path("subscriptions/", include('subscriptions.urls')),
    path("communication/", include('communication.api_urls')),
]
