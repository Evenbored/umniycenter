from django.contrib import admin

from .models import Courses

# Register your models here.
@admin.register(Courses)
class CoursesAdmin(admin.ModelAdmin):
    list_display = ['name']
