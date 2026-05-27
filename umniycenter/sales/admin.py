from django.contrib import admin

from .models import Lead, Order, OrderItem


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'child_fio', 'parent_fio', 'phone', 'status', 'assigned_to', 'source', 'created_at')
    list_filter = ('status', 'source', 'assigned_to', 'created_at')
    search_fields = ('child_fio', 'parent_fio', 'phone', 'email')
    filter_horizontal = ('courses',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'student', 'parent', 'total_amount', 'paid_amount', 'paid_at', 'created_at')
    list_filter = ('status', 'created_at', 'paid_at')
    search_fields = ('student__first_name', 'student__last_name', 'parent__first_name', 'parent__last_name', 'comment')
    inlines = (OrderItemInline,)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'item_type', 'title', 'unit_price', 'amount', 'quantity', 'lesson', 'schedule', 'subscription')
    list_filter = ('item_type', 'created_at')
    search_fields = ('title',)
