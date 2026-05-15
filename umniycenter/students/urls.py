from django.urls import path

from .api_views import MyStudentsAPIView, StudentsCountAPIView
from . import views

app_name = 'students'

urlpatterns = [
    path('students/', views.students_view, name='students_view'),
]
