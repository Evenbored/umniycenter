from django.contrib import admin
from .models import Tariff, Subscription, Payment, Refund, LessonAttendance, SubscriptionFreeze, SubscriptionLog


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'subscription_type', 'lessons_count', 'validity_days', 'price', 'allow_negative_lessons', 'allow_group_to_individual', 'is_trial', 'is_active']
    list_filter = ['is_active', 'is_trial', 'subscription_type', 'allow_negative_lessons', 'allow_group_to_individual', 'course']
    search_fields = ['name', 'course__name']
    list_editable = ['is_active', 'is_trial']
    fields = ['name', 'course', 'subscription_type', 'lessons_count', 'validity_days', 'price', 'description', 'allow_negative_lessons', 'default_negative_limit', 'allow_group_to_individual', 'group_to_individual_ratio', 'is_trial', 'is_active']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'tariff', 'group', 'lessons_used', 'lessons_total', 'get_lessons_remaining', 'negative_limit', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'tariff__course', 'tariff__subscription_type', 'group', 'allow_negative_lessons', 'allow_group_to_individual', 'start_date', 'end_date']
    search_fields = ['student__username', 'student__first_name', 'student__last_name', 'parent__username']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'student', 'parent', 'tariff', 'group',
        'lessons_total', 'lessons_used',
        'start_date', 'end_date',
        'status',
        'frozen_at', 'frozen_days', 'frozen_until', 'freeze_reason',
        'allow_negative_lessons', 'negative_limit', 'allow_group_to_individual', 'group_to_individual_ratio',
        'created_at', 'updated_at'
    ]
    
    def get_lessons_remaining(self, obj):
        return obj.lessons_remaining
    get_lessons_remaining.short_description = 'Осталось занятий'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'subscription', 'parent', 'amount', 'payment_method', 'status', 'paid_at', 'created_at']
    list_filter = ['status', 'payment_method', 'paid_at']
    search_fields = ['parent__username', 'parent__first_name', 'parent__last_name', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'order', 'subscription', 'parent',
        'amount', 'payment_method', 'status',
        'transaction_id', 'notes',
        'paid_at', 'created_at', 'updated_at'
    ]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'payment', 'order', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['payment__transaction_id', 'payment__yookassa_payment_id', 'reason']


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


@admin.register(SubscriptionFreeze)
class SubscriptionFreezeAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'start_date', 'end_date', 'days', 'created_by', 'created_at']
    list_filter = ['start_date', 'end_date', 'created_at']
    search_fields = ['subscription__student__first_name', 'subscription__student__last_name', 'reason']


@admin.register(SubscriptionLog)
class SubscriptionLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'action', 'lessons_delta', 'balance_after', 'created_by', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['subscription__student__first_name', 'subscription__student__last_name', 'comment']
