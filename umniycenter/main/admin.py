from django.contrib import admin
from .models import *
# Register your models here.
@admin.register(ParticipantRequest)
class ParticipantRequestAdmin(admin.ModelAdmin):
    list_display = ['parent_fio', 'child_fio', 'phone', 'age', 'get_courses_display', 'created', 'checked']
    list_editable = ['checked']
    list_filter = ['checked', 'created']
    search_fields = ['child_fio', 'parent_fio', 'phone', 'email']
    filter_horizontal = ['courses']
    
    def get_courses_display(self, obj):
        return obj.get_courses_display()
    get_courses_display.short_description = 'Курсы'