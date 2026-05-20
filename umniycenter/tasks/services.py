from django.utils import timezone

from .models import Task, TaskPriority, TaskStatus, TaskType


class TaskService:
    @staticmethod
    def create_for_lead(lead, assignee=None, author=None, due_at=None):
        assignee = assignee or lead.assigned_to or author
        due_at = due_at or timezone.now() + timezone.timedelta(hours=2)
        existing = Task.objects.filter(lead=lead, task_type=TaskType.CALL, status__in=[TaskStatus.NEW, TaskStatus.IN_PROGRESS]).first()
        if existing:
            return existing, False
        task = Task.objects.create(
            title=f'Связаться с лидом: {lead.child_fio}',
            description=f'Родитель: {lead.parent_fio}\nТелефон: {lead.phone}',
            task_type=TaskType.CALL,
            priority=TaskPriority.HIGH,
            assignee=assignee,
            author=author,
            due_at=due_at,
            lead=lead,
        )
        return task, True

    @staticmethod
    def create_for_subscription_renewal(subscription, assignee=None, author=None, due_at=None, reason=''):
        due_at = due_at or timezone.now() + timezone.timedelta(days=1)
        existing = Task.objects.filter(
            subscription=subscription,
            task_type=TaskType.RENEWAL,
            status__in=[TaskStatus.NEW, TaskStatus.IN_PROGRESS],
        ).first()
        if existing:
            return existing, False

        student_name = subscription.student.get_full_name() or subscription.student.username
        course_name = subscription.tariff.course.name if subscription.tariff_id and subscription.tariff.course_id else 'курс не указан'
        details = [
            f'Ученик: {student_name}',
            f'Тариф: {subscription.tariff.name}',
            f'Курс: {course_name}',
            f'Осталось занятий: {subscription.lessons_remaining}',
            f'Дата окончания: {subscription.end_date:%d.%m.%Y}',
        ]
        if reason:
            details.insert(0, reason)

        task = Task.objects.create(
            title=f'Продлить абонемент: {student_name}',
            description='\n'.join(details),
            task_type=TaskType.RENEWAL,
            priority=TaskPriority.HIGH,
            assignee=assignee,
            author=author,
            due_at=due_at,
            subscription=subscription,
            student=subscription.student,
            parent=subscription.parent,
        )
        return task, True
