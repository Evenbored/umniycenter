from django.urls import path
from .views import *

urlpatterns = [
    path("", CourseListAPIView.as_view(), name="courses"),
    path("create/", create_course, name="create_course"),
    path("<int:course_id>/", update_course, name="update_course"),
    path("<int:course_id>/delete/", delete_course, name="delete_course"),
]
