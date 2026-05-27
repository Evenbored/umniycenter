from rest_framework import serializers

from sales.models import Order, OrderItem
from subscriptions.api.serializers import PaymentSerializer, SubscriptionSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    tariff_name = serializers.CharField(source='tariff.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'item_type', 'title', 'quantity', 'unit_price', 'amount', 'course', 'course_name', 'tariff', 'tariff_name', 'subscription', 'lesson', 'metadata', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.get_full_name', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'parent', 'parent_name', 'student', 'student_name', 'status', 'total_amount', 'paid_amount', 'paid_at', 'comment', 'created_by', 'created_at', 'updated_at', 'items', 'payments']
