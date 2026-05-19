from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'child_fio', 'parent_fio', 'phone', 'status', 'assigned_to', 'source', 'created_at')
    list_filter = ('status', 'source', 'assigned_to', 'created_at')
    search_fields = ('child_fio', 'parent_fio', 'phone', 'email')
    filter_horizontal = ('courses',)
