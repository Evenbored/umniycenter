from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'task_type', 'status', 'priority', 'assignee', 'due_at', 'created_at')
    list_filter = ('status', 'task_type', 'priority', 'assignee')
    search_fields = ('title', 'description')
