from django.contrib import admin
from .models import Ticket, Message


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'parent', 'assigned_admin', 'category', 'subject', 'status', 'created_at', 'last_message_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['parent__first_name', 'parent__last_name', 'subject']
    readonly_fields = ['created_at', 'updated_at', 'last_message_at', 'closed_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('parent', 'assigned_admin', 'category', 'subject', 'status')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at', 'last_message_at', 'closed_at', 'closed_by')
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'ticket', 'sender', 'content_preview', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['content', 'sender__first_name', 'sender__last_name']
    readonly_fields = ['created_at', 'read_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержание'
