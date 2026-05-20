from django.db import models
from django.utils import timezone

from accounts.models import CustomUser


class TaskType(models.TextChoices):
    CALL = 'call', 'Звонок'
    MESSAGE = 'message', 'Сообщение'
    PAYMENT = 'payment', 'Оплата'
    RENEWAL = 'renewal', 'Продление абонемента'
    TRIAL = 'trial', 'Пробное занятие'
    ABSENCE = 'absence', 'Пропуск занятия'
    SCHEDULE = 'schedule', 'Расписание'
    DOCUMENT = 'document', 'Документ'
    OTHER = 'other', 'Другое'


class TaskStatus(models.TextChoices):
    NEW = 'new', 'Новая'
    IN_PROGRESS = 'in_progress', 'В работе'
    DONE = 'done', 'Выполнена'
    CANCELED = 'canceled', 'Отменена'


class TaskPriority(models.TextChoices):
    LOW = 'low', 'Низкий'
    MEDIUM = 'medium', 'Средний'
    HIGH = 'high', 'Высокий'


class Task(models.Model):
    title = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    task_type = models.CharField(max_length=24, choices=TaskType.choices, default=TaskType.OTHER, verbose_name='Тип')
    status = models.CharField(max_length=24, choices=TaskStatus.choices, default=TaskStatus.NEW, verbose_name='Статус')
    priority = models.CharField(max_length=16, choices=TaskPriority.choices, default=TaskPriority.MEDIUM, verbose_name='Приоритет')
    assignee = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks', verbose_name='Ответственный')
    author = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tasks', verbose_name='Автор')
    due_at = models.DateTimeField(null=True, blank=True, verbose_name='Срок выполнения')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения')
    lead = models.ForeignKey('sales.Lead', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Лид')
    student = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_tasks', verbose_name='Ученик')
    parent = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='parent_tasks', verbose_name='Родитель')
    payment = models.ForeignKey('subscriptions.Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Платеж')
    subscription = models.ForeignKey('subscriptions.Subscription', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Абонемент')
    lesson = models.ForeignKey('schedule.Schedule', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Занятие')
    ticket = models.ForeignKey('communication.Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Обращение')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['status', 'due_at', '-created_at']
        indexes = [
            models.Index(fields=['assignee', 'status', 'due_at']),
            models.Index(fields=['status', 'due_at']),
            models.Index(fields=['task_type']),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return bool(self.due_at and self.due_at < timezone.now() and self.status not in [TaskStatus.DONE, TaskStatus.CANCELED])

    def complete(self):
        self.status = TaskStatus.DONE
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
