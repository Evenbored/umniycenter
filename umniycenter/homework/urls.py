from django.urls import path
from . import views

app_name = 'homework'

urlpatterns = [
    path('homework/', views.homework_view, name='homework_view'),
    path('homework/create', views.homework_create, name='homework_create'),
]