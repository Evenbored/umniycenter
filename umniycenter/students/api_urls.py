from django.urls import path
from .api_views import *

urlpatterns = [
    path("my/", MyStudentsAPIView.as_view(), name="my_students"),
    path("", create_student, name="create_student"),
    path("count/", StudentsCountAPIView.as_view(), name="students_count"),
    path("<int:student_id>/", update_student, name="update_student"),
    path("<int:student_id>/groups/", add_student_to_group, name="add_student_to_group"),
    path("<int:student_id>/groups/<int:membership_id>/", remove_student_from_group, name="remove_student_from_group"),
]
