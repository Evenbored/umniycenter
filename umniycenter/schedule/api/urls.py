from django.urls import path
from .views import *

urlpatterns = [
    path("my/", MyScheduleAPIView.as_view(), name="my_schedule"),
    path("", CrmScheduleAPIView.as_view(), name="schedule_list"),
    path("create/", create_crm_lesson, name="schedule_create"),
    path("generate/", generate_crm_schedule, name="schedule_generate"),
    path("teachers/", teacher_options, name="schedule_teachers"),
    path("students/", student_options, name="schedule_students"),
    path("<int:lesson_id>/cancel/", cancel_lesson, name="schedule_cancel"),
    path("<int:lesson_id>/reschedule/", reschedule_lesson, name="schedule_reschedule"),
    path("<int:lesson_id>/attendance/", lesson_attendance_context, name="schedule_attendance"),
    path("participants/<int:participant_id>/attendance/", mark_participant_attendance, name="schedule_participant_attendance"),
    path("participants/<int:participant_id>/cancel-attendance/", cancel_participant_attendance, name="schedule_participant_cancel_attendance"),
    path("templates/", GroupScheduleTemplateListAPIView.as_view(), name="schedule_templates"),
    path("templates/create/", create_group_schedule_template, name="schedule_template_create"),
    path("templates/<int:pk>/", GroupScheduleTemplateDetailAPIView.as_view(), name="schedule_template_detail"),
]
