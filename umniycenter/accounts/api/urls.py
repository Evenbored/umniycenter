from django.urls import path
from .views import *

urlpatterns = [
    path("users/me/", CurrentUserAPIView.as_view(), name="user_me"),
    path("users/", UserListAPIView.as_view(), name="users"),
    path("teachers/", TeachersListAPIView.as_view(), name="teachers"),
    path("teachers/create/", create_teacher, name="create_teacher"),
    path("teachers/<int:teacher_id>/", teacher_detail, name="teacher_detail"),
    path("parents/", ParentsListAPIView.as_view(), name="parents"),
    path("parents/<int:parent_id>/", update_parent, name="update_parent"),
]
