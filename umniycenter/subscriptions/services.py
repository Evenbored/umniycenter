from django.db import transaction
from django.utils import timezone

from .models import Subscription, Tariff, SubscriptionLog


class SubscriptionService:
    """Бизнес-логика абонементов: подбор, списание, заморозка."""

    @staticmethod
    def lesson_course(lesson):
        return lesson.group.course if lesson.group_id else lesson.course

    @staticmethod
    def find_subscription_for_lesson(student, lesson, base_lessons_count=1):
        course = SubscriptionService.lesson_course(lesson)
        if not course:
            return None, base_lessons_count

        today = timezone.now().date()
        qs = (
            Subscription.objects.select_related('tariff', 'tariff__course', 'group')
            .filter(
                student=student,
                status='active',
                tariff__course=course,
                end_date__gte=today,
            )
            .order_by('end_date', 'created_at')
        )

        # Групповое занятие: сначала абонемент конкретной группы, потом любой групповой по курсу.
        if lesson.group_id:
            subscriptions = qs.filter(tariff__subscription_type=Tariff.SUBSCRIPTION_TYPE_GROUP)
            exact = subscriptions.filter(group=lesson.group).first()
            return (exact or subscriptions.first()), base_lessons_count

        # Индивидуальное занятие: сначала индивидуальный абонемент.
        individual = qs.filter(tariff__subscription_type=Tariff.SUBSCRIPTION_TYPE_INDIVIDUAL).first()
        if individual:
            return individual, base_lessons_count

        # Потом разрешенный групповой абонемент с коэффициентом.
        group_subscription = qs.filter(
            tariff__subscription_type=Tariff.SUBSCRIPTION_TYPE_GROUP,
            allow_group_to_individual=True,
        ).first()
        if group_subscription:
            return group_subscription, base_lessons_count * group_subscription.group_to_individual_ratio

        return None, base_lessons_count

    @staticmethod
    @transaction.atomic
    def deduct_for_lesson(student, lesson, base_lessons_count=1, marked_by=None):
        subscription, lessons_to_deduct = SubscriptionService.find_subscription_for_lesson(
            student,
            lesson,
            base_lessons_count,
        )
        if not subscription:
            raise ValueError("У ученика нет подходящего активного абонемента на этот курс")

        subscription = Subscription.objects.select_for_update().get(id=subscription.id)
        if not subscription.can_deduct_lessons(lessons_to_deduct):
            if subscription.allow_negative_lessons:
                raise ValueError(
                    f"Недостаточно занятий. Осталось: {subscription.lessons_remaining}, "
                    f"лимит минуса: {subscription.negative_limit}, требуется: {lessons_to_deduct}"
                )
            raise ValueError(f"Недостаточно занятий. Осталось: {subscription.lessons_remaining}, требуется: {lessons_to_deduct}")

        subscription.deduct_lessons(lessons_to_deduct)
        SubscriptionLog.log(
            subscription,
            'deduct',
            lessons_delta=-lessons_to_deduct,
            related_lesson=lesson,
            created_by=marked_by,
        )
        return subscription, lessons_to_deduct

    @staticmethod
    @transaction.atomic
    def refund_for_attendance(attendance, created_by=None):
        subscription = attendance.subscription
        if not subscription:
            return False
        subscription = Subscription.objects.select_for_update().get(id=subscription.id)
        refunded = subscription.refund_lessons(attendance.lessons_count)
        if refunded:
            SubscriptionLog.log(
                subscription,
                'refund',
                lessons_delta=attendance.lessons_count,
                related_lesson=attendance.schedule,
                created_by=created_by,
            )
        return refunded
