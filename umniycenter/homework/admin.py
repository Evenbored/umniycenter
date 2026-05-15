from django.contrib import admin

from .models import HomeWorkStudents, Homework

# Register your models here.
@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ['task', 'group', 'created', 'finished']


@admin.register(HomeWorkStudents)
class HomeWorkStudentsAdmin(admin.ModelAdmin):
    list_display = ['homework', 'student']