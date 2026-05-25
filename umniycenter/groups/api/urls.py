from django.urls import path
from .views import *

urlpatterns = [
    path("my/", MyGroupsAPIView.as_view(), name="my_groups"),
    path("count/", GroupsCountAPIView.as_view(), name="groups_count"),
    path("create/", create_group, name="create_group"),
    path("<int:group_id>/", update_group, name="update_group"),
]
