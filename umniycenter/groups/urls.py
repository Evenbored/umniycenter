from django.urls import path

from .api.views import GroupsCountAPIView, MyGroupsAPIView, create_group, update_group
from . import views

app_name = 'groups'

urlpatterns = [
    path('grade/', views.grades_view, name="grade"),
]
