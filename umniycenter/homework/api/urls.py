from django.urls import path
from .views import *

urlpatterns = [
    path("", HomeworkListAPIView.as_view(), name="homework"),
    path("my/", MyHomeworkAPIView.as_view(), name="my_homework"),
]
