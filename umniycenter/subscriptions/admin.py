from django.contrib import admin
from .models import Tariff, Subscription, Payment, LessonAttendance


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'lessons_count', 'validity_days', 'price', 'is_trial', 'is_active']
    list_filter = ['is_active', 'is_trial', 'course']
    search_fields = ['name', 'course__name']
    list_editable = ['is_active', 'is_trial']
    fields = ['name', 'course', 'lessons_count', 'validity_days', 'price', 'description', 'is_trial', 'is_active']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'tariff', 'lessons_used', 'lessons_total', 'get_lessons_remaining', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'tariff__course', 'start_date', 'end_date']
    search_fields = ['student__username', 'student__first_name', 'student__last_name', 'parent__username']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'student', 'parent', 'tariff',
        'lessons_total', 'lessons_used',
        'start_date', 'end_date',
        'status',
        'frozen_at', 'frozen_days',
        'created_at', 'updated_at'
    ]
    
    def get_lessons_remaining(self, obj):
        return obj.lessons_remaining
    get_lessons_remaining.short_description = 'Осталось занятий'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'parent', 'amount', 'payment_method', 'status', 'paid_at', 'created_at']
    list_filter = ['status', 'payment_method', 'paid_at']
    search_fields = ['parent__username', 'parent__first_name', 'parent__last_name', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'subscription', 'parent',
        'amount', 'payment_method', 'status',
        'transaction_id', 'notes',
        'paid_at', 'created_at', 'updated_at'
    ]


@admin.register(LessonAttendance)
class LessonAttendanceAdmin(admin.ModelAdmin):
    list_display = ['id', 'schedule', 'student', 'status', 'lessons_count', 'lesson_deducted', 'subscription', 'marked_by', 'created_at']
    list_filter = ['status', 'lesson_deducted', 'lessons_count', 'created_at']
    search_fields = ['student__username', 'student__first_name', 'student__last_name', 'schedule__group__course__name']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'schedule', 'student', 'subscription',
        'status', 'lessons_count', 'lesson_deducted',
        'notes', 'marked_by',
        'created_at', 'updated_at'
    ]
