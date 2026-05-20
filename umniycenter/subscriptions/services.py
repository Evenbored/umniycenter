from django.db import transaction
from django.db.models import F
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


class SubscriptionMonitoringService:
    """Ежедневный контроль сроков, остатков и статусов абонементов."""

    LOW_LESSONS_THRESHOLD = 2
    EXPIRING_DAYS_THRESHOLD = 7

    @classmethod
    def get_risk_queryset(cls, today=None):
        today = today or timezone.now().date()
        return {
            'low_lessons': Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(
                status='active',
                lessons_used__gte=F('lessons_total') - cls.LOW_LESSONS_THRESHOLD,
            ),
            'expiring_soon': Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(
                status='active',
                end_date__gte=today,
                end_date__lte=today + timezone.timedelta(days=cls.EXPIRING_DAYS_THRESHOLD),
            ),
            'expired_by_date': Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(
                status='active',
                end_date__lt=today,
            ),
            'exhausted_by_lessons': Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(
                status='active',
                allow_negative_lessons=False,
                lessons_used__gte=F('lessons_total'),
            ),
            'pending_payment': Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(
                status='pending',
            ),
            'negative_balance': Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(
                status='active',
                lessons_used__gt=F('lessons_total'),
            ),
        }

    @classmethod
    @transaction.atomic
    def run_daily_check(cls, created_by=None, today=None, write_logs=True):
        today = today or timezone.now().date()
        risks = cls.get_risk_queryset(today=today)
        expired_ids = list(risks['expired_by_date'].values_list('id', flat=True))
        exhausted_ids = list(risks['exhausted_by_lessons'].values_list('id', flat=True))
        expired_count = 0
        exhausted_count = 0

        for subscription in Subscription.objects.select_for_update().filter(id__in=expired_ids):
            if subscription.status != 'active':
                continue
            subscription.status = 'expired'
            subscription.save(update_fields=['status', 'updated_at'])
            expired_count += 1
            if write_logs:
                SubscriptionLog.log(subscription, 'expired', comment='Автоматическая проверка: истек срок действия', created_by=created_by)
            subscription.student.update_active_status()
            subscription.parent.update_active_status()

        for subscription in Subscription.objects.select_for_update().filter(id__in=exhausted_ids).exclude(id__in=expired_ids):
            if subscription.status != 'active':
                continue
            subscription.status = 'exhausted'
            subscription.save(update_fields=['status', 'updated_at'])
            exhausted_count += 1
            if write_logs:
                SubscriptionLog.log(subscription, 'exhausted', comment='Автоматическая проверка: занятия закончились', created_by=created_by)
            subscription.student.update_active_status()
            subscription.parent.update_active_status()

        refreshed_risks = cls.get_risk_queryset(today=today)
        tasks_created = 0
        try:
            from accounts.models import CustomUser, UserRole
            from tasks.services import TaskService

            assignee = CustomUser.objects.filter(role=UserRole.ADMIN, is_active=True).order_by('id').first()
            renewal_subscription_ids = set(refreshed_risks['low_lessons'].values_list('id', flat=True))
            renewal_subscription_ids.update(refreshed_risks['expiring_soon'].values_list('id', flat=True))

            renewal_subscriptions = Subscription.objects.select_related('student', 'parent', 'tariff', 'tariff__course').filter(id__in=renewal_subscription_ids)
            for subscription in renewal_subscriptions:
                reasons = []
                if subscription.lessons_remaining <= cls.LOW_LESSONS_THRESHOLD:
                    reasons.append(f'Осталось {subscription.lessons_remaining} занятий')
                if subscription.end_date <= today + timezone.timedelta(days=cls.EXPIRING_DAYS_THRESHOLD):
                    reasons.append(f'Абонемент заканчивается {subscription.end_date:%d.%m.%Y}')
                _, created = TaskService.create_for_subscription_renewal(
                    subscription,
                    assignee=assignee,
                    author=created_by,
                    due_at=timezone.now() + timezone.timedelta(days=1),
                    reason='; '.join(reasons),
                )
                if created:
                    tasks_created += 1
        except Exception:
            tasks_created = 0

        return {
            'expired_updated': expired_count,
            'exhausted_updated': exhausted_count,
            'low_lessons': refreshed_risks['low_lessons'].count(),
            'expiring_soon': refreshed_risks['expiring_soon'].count(),
            'pending_payment': refreshed_risks['pending_payment'].count(),
            'negative_balance': refreshed_risks['negative_balance'].count(),
            'tasks_created': tasks_created,
            'checked_at': timezone.now(),
        }
