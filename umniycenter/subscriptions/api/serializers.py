from rest_framework import serializers
from ..models import Tariff, Subscription, Payment, LessonAttendance
from schedule.models import LessonParticipant
from accounts.models import CustomUser
from courses.models import Courses


class TariffSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    subscription_type_display = serializers.CharField(source='get_subscription_type_display', read_only=True)
    
    class Meta:
        model = Tariff
        fields = [
            'id', 'name', 'course', 'course_name',
            'lessons_count', 'validity_days', 'price',
            'description', 'subscription_type', 'subscription_type_display', 'is_active', 'is_trial',
            'allow_negative_lessons', 'default_negative_limit', 'allow_group_to_individual', 'group_to_individual_ratio',
            'created_at', 'updated_at'
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    parent_name = serializers.CharField(source='parent.get_full_name', read_only=True)
    tariff_name = serializers.CharField(source='tariff.name', read_only=True)
    course_name = serializers.CharField(source='tariff.course.name', read_only=True)
    subscription_type = serializers.CharField(source='tariff.subscription_type', read_only=True)
    subscription_type_display = serializers.CharField(source='tariff.get_subscription_type_display', read_only=True)
    lessons_remaining = serializers.IntegerField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    group_name = serializers.CharField(source='group.number', read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'student', 'student_name', 'parent', 'parent_name',
            'tariff', 'tariff_name', 'course_name', 'group', 'group_name',
            'subscription_type', 'subscription_type_display',
            'lessons_total', 'lessons_used', 'lessons_remaining',
            'start_date', 'end_date', 'status', 'is_valid',
            'frozen_at', 'frozen_days', 'frozen_until', 'freeze_reason',
            'closed_at', 'closed_by', 'close_reason',
            'allow_negative_lessons', 'negative_limit', 'negative_used', 'negative_available',
            'allow_group_to_individual', 'group_to_individual_ratio',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['lessons_used', 'status', 'created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.get_full_name', read_only=True)
    parent_phone = serializers.CharField(source='parent.phone', read_only=True)
    parent_email = serializers.EmailField(source='parent.email', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    yookassa_payment_url = serializers.URLField(read_only=True)
    yookassa_payment_id = serializers.CharField(read_only=True)
    subscription_info = serializers.SerializerMethodField()
    order_info = serializers.SerializerMethodField()
    items_info = serializers.SerializerMethodField()
    
    def get_subscription_info(self, obj):
        subscription = obj.subscription
        if not subscription and obj.order_id:
            item = obj.order.items.filter(subscription__isnull=False).select_related('subscription', 'subscription__student', 'subscription__tariff', 'subscription__tariff__course').first()
            subscription = item.subscription if item else None
        if not subscription:
            return None
        return {
            'id': subscription.id,
            'student_name': subscription.student.get_full_name(),
            'student_id': subscription.student_id,
            'tariff_name': subscription.tariff.name,
            'course_name': subscription.tariff.course.name,
            'subscription_type': subscription.tariff.subscription_type,
            'subscription_type_display': subscription.tariff.get_subscription_type_display(),
            'subscription_status': subscription.status,
            'lessons_total': subscription.lessons_total,
            'lessons_used': subscription.lessons_used,
            'lessons_remaining': subscription.lessons_remaining,
            'start_date': subscription.start_date,
            'end_date': subscription.end_date,
        }

    def get_order_info(self, obj):
        if not obj.order_id:
            return None
        return {'id': obj.order_id, 'status': obj.order.status, 'total_amount': obj.order.total_amount, 'paid_amount': obj.order.paid_amount, 'student_id': obj.order.student_id, 'parent_id': obj.order.parent_id}

    def get_items_info(self, obj):
        if not obj.order_id:
            return []
        return [{'id': item.id, 'item_type': item.item_type, 'title': item.title, 'amount': item.amount, 'quantity': item.quantity, 'subscription': item.subscription_id, 'lesson': item.lesson_id} for item in obj.order.items.all()]
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_info', 'items_info', 'subscription', 'subscription_info',
            'parent', 'parent_name',
            'parent_phone', 'parent_email',
            'amount', 'payment_method', 'payment_method_display', 'status', 'status_display',
            'transaction_id', 'yookassa_payment_id', 'yookassa_payment_url', 'notes', 'error_message',
            'paid_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LessonAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    schedule_info = serializers.SerializerMethodField()
    marked_by_name = serializers.SerializerMethodField()
    
    def get_schedule_info(self, obj):
        if isinstance(obj, LessonParticipant):
            lesson = obj.lesson
            group = lesson.group
            course = lesson.course
            return {
                'id': lesson.id,
                'date': lesson.starts_at,
                'group': lesson.title,
                'course': course.name if course else '',
                'lesson_type': lesson.lesson_type,
                'is_single': lesson.is_single,
            }
        group = obj.schedule.group
        course = group.course if group else obj.schedule.course
        return {
            'id': obj.schedule.id,
            'date': obj.schedule.classdateStart,
            'group': obj.schedule.title,
            'course': course.name if course else '',
            'lesson_type': obj.schedule.lesson_type,
            'is_single': obj.schedule.is_single,
        }

    def get_marked_by_name(self, obj):
        if obj.marked_by:
            return obj.marked_by.get_full_name() or obj.marked_by.username
        return ''
    
    class Meta:
        model = LessonAttendance
        fields = [
            'id', 'schedule', 'schedule_info',
            'student', 'student_name',
            'subscription', 'status', 'lessons_count',
            'lesson_deducted', 'notes',
            'marked_by', 'marked_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['lesson_deducted', 'created_at', 'updated_at']

    def to_representation(self, instance):
        if isinstance(instance, LessonParticipant):
            return {
                'id': instance.id,
                'schedule': instance.lesson_id,
                'schedule_info': self.get_schedule_info(instance),
                'student': instance.student_id,
                'student_name': instance.student.get_full_name(),
                'subscription': instance.subscription_id,
                'status': instance.attendance_status,
                'lessons_count': instance.lessons_to_charge,
                'lesson_deducted': instance.lessons_charged,
                'notes': instance.notes,
                'marked_by': instance.marked_by_id,
                'marked_by_name': instance.marked_by.get_full_name() if instance.marked_by else '',
                'created_at': instance.created_at,
                'updated_at': instance.updated_at,
            }
        return super().to_representation(instance)


class CreateSubscriptionSerializer(serializers.Serializer):
    """Serializer для создания подписки с платежом"""
    student_id = serializers.IntegerField()
    parent_id = serializers.IntegerField()
    tariff_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES)
    payment_status = serializers.ChoiceField(
        choices=Payment.STATUS_CHOICES,
        default='completed'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_student_id(self, value):
        try:
            student = CustomUser.objects.get(id=value, role=1)  # STUDENT
            return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Ученик не найден")
    
    def validate_parent_id(self, value):
        try:
            parent = CustomUser.objects.get(id=value, role=3)  # PARENT
            return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Родитель не найден")
    
    def validate_tariff_id(self, value):
        try:
            tariff = Tariff.objects.get(id=value, is_active=True)
            return value
        except Tariff.DoesNotExist:
            raise serializers.ValidationError("Тариф не найден или неактивен")
