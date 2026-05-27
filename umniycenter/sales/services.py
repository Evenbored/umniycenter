from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from accounts.models import UserRole
from schedule.models import Lesson, Schedule
from .models import Order, OrderItem, OrderItemType, OrderStatus


class OrderService:
    @staticmethod
    def get_effective_paid_date(payment):
        return payment.paid_at or payment.created_at

    @staticmethod
    def create_subscription_order(payment, created_by=None):
        if payment.order_id:
            OrderService.update_order_payment_status(payment.order)
            return payment.order
        subscription = payment.subscription
        paid_at = OrderService.get_effective_paid_date(payment) if payment.status == 'completed' else None
        status = OrderStatus.PAID if payment.status == 'completed' else OrderStatus.PENDING

        order, _ = Order.objects.update_or_create(
            payment=payment,
            defaults={
                'parent': payment.parent,
                'student': subscription.student,
                'status': status,
                'total_amount': payment.amount,
                'paid_amount': payment.amount if payment.status == 'completed' else 0,
                'paid_at': paid_at,
                'created_by': created_by,
                'comment': f'Оплата абонемента #{subscription.id}',
            },
        )
        OrderItem.objects.update_or_create(
            order=order,
            subscription=subscription,
            item_type=OrderItemType.SUBSCRIPTION,
            defaults={
                'title': subscription.tariff.name,
                'amount': payment.amount,
                'quantity': 1,
                'course': subscription.tariff.course,
                'tariff': subscription.tariff,
                'metadata': {
                    'payment_id': payment.id,
                    'tariff_id': subscription.tariff_id,
                    'subscription_type': subscription.tariff.subscription_type,
                },
            },
        )
        return order

    @staticmethod
    @transaction.atomic
    def create_single_lesson_order(
        *,
        lesson=None,
        schedule=None,
        student=None,
        parent=None,
        amount,
        payment_method='cash',
        paid=True,
        created_by=None,
        comment='',
    ):
        target = lesson or schedule
        if lesson and not lesson.is_single:
            raise ValueError('Заказ разового занятия можно создать только для разового занятия')
        if schedule and schedule.lesson_type != Schedule.LESSON_TYPE_SINGLE and not schedule.is_single:
            raise ValueError('Заказ разового занятия можно создать только для разового занятия')

        amount = Decimal(amount or 0)
        if amount <= 0:
            raise ValueError('Укажите стоимость разового занятия')

        if student is None:
            student = getattr(target, 'student', None)

        if parent is None and student is not None:
            try:
                parent_profile = student.student_profile.parents.first()
                parent = parent_profile.user if parent_profile else None
            except Exception:
                parent = None

        status = OrderStatus.PAID if paid else OrderStatus.PENDING
        paid_at = timezone.now() if paid else None
        item_type = OrderItemType.SINGLE_GROUP if target.group_id else OrderItemType.SINGLE_INDIVIDUAL
        title = f'{target.get_lesson_type_display()} · {target.course_name or "Без курса"}'

        order = Order.objects.create(
            parent=parent,
            student=student,
            status=status,
            total_amount=amount,
            paid_amount=amount if paid else 0,
            paid_at=paid_at,
            created_by=created_by,
            comment=comment,
        )
        OrderItem.objects.create(
            order=order,
            item_type=item_type,
            title=title,
            amount=amount,
            unit_price=amount,
            quantity=1,
            course=target.group.course if target.group_id else target.course,
            schedule=schedule,
            lesson=lesson,
            metadata={
                'payment_method': payment_method,
                'teacher_id': target.teacher_id,
                'group_id': target.group_id,
                'student_id': getattr(student, 'id', None),
                'starts_at': getattr(target, 'starts_at', None).isoformat() if getattr(target, 'starts_at', None) else None,
            },
        )
        return order

    @staticmethod
    @transaction.atomic
    def create_subscription_order_new(student, parent, tariff, group=None, created_by=None, comment=''):
        from datetime import timedelta
        from subscriptions.models import Subscription

        subscription = Subscription.objects.create(
            student=student,
            parent=parent,
            tariff=tariff,
            group=group,
            lessons_total=tariff.lessons_count,
            lessons_used=0,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=tariff.validity_days),
            status='pending',
            allow_negative_lessons=tariff.allow_negative_lessons,
            negative_limit=tariff.default_negative_limit,
            allow_group_to_individual=tariff.allow_group_to_individual,
            group_to_individual_ratio=tariff.group_to_individual_ratio,
        )
        order = Order.objects.create(parent=parent, student=student, status=OrderStatus.PENDING_PAYMENT, total_amount=tariff.price, paid_amount=0, created_by=created_by, comment=comment)
        OrderItem.objects.create(order=order, item_type=OrderItemType.SUBSCRIPTION, title=tariff.name, quantity=1, unit_price=tariff.price, amount=tariff.price, course=tariff.course, tariff=tariff, subscription=subscription, metadata={'subscription_type': tariff.subscription_type})
        return order, subscription

    @staticmethod
    def recalculate_order(order):
        total = sum(item.amount for item in order.items.all())
        order.total_amount = total
        order.save(update_fields=['total_amount', 'updated_at'])
        return order

    @staticmethod
    def update_order_payment_status(order):
        paid_amount = sum(payment.amount for payment in order.payments.filter(status='completed'))
        order.paid_amount = paid_amount
        if paid_amount <= 0:
            order.status = OrderStatus.PENDING_PAYMENT
            order.paid_at = None
        elif paid_amount < order.total_amount:
            order.status = OrderStatus.PARTIALLY_PAID
            order.paid_at = None
        else:
            order.status = OrderStatus.PAID
            order.paid_at = order.paid_at or timezone.now()
        order.save(update_fields=['paid_amount', 'status', 'paid_at', 'updated_at'])
        return order

    @staticmethod
    def sync_completed_subscription_orders(created_by=None):
        from subscriptions.models import Payment

        for payment in Payment.objects.filter(status='completed').select_related('subscription', 'subscription__tariff', 'subscription__tariff__course', 'subscription__student', 'parent'):
            OrderService.create_subscription_order(payment, created_by=created_by)
