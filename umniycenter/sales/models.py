from django.db import models
from django.utils import timezone

from accounts.models import CustomUser, LeadSource, UserRole
from courses.models import Courses
from main.models import ParticipantRequest


class LeadStatus(models.TextChoices):
    NEW = 'new', 'Новая'
    IN_PROGRESS = 'in_progress', 'В работе'
    NO_ANSWER = 'no_answer', 'Не дозвонились'
    CONTACTED = 'contacted', 'Контакт установлен'
    TRIAL_SCHEDULED = 'trial_scheduled', 'Пробное назначено'
    TRIAL_COMPLETED = 'trial_completed', 'Пробное проведено'
    WAITING_DECISION = 'waiting_decision', 'Клиент думает'
    CONVERTED = 'converted', 'Купил абонемент'
    LOST = 'lost', 'Отказ'
    ARCHIVED = 'archived', 'Архив'


class Lead(models.Model):
    participant_request = models.OneToOneField(
        ParticipantRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead',
        verbose_name='Исходная заявка',
    )
    parent_fio = models.CharField(max_length=150, verbose_name='ФИО родителя')
    child_fio = models.CharField(max_length=150, verbose_name='ФИО ребенка')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name='Email')
    age = models.CharField(max_length=3, blank=True, verbose_name='Возраст ребенка')
    courses = models.ManyToManyField(Courses, blank=True, related_name='leads', verbose_name='Интересующие курсы')
    source = models.CharField(max_length=20, choices=LeadSource.choices, blank=True, null=True, verbose_name='Источник')
    status = models.CharField(max_length=32, choices=LeadStatus.choices, default=LeadStatus.NEW, verbose_name='Статус')
    assigned_to = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
        limit_choices_to={'role': UserRole.ADMIN},
        verbose_name='Ответственный',
    )
    next_contact_at = models.DateTimeField(null=True, blank=True, verbose_name='Следующий контакт')
    last_contact_at = models.DateTimeField(null=True, blank=True, verbose_name='Последний контакт')
    lost_reason = models.CharField(max_length=255, blank=True, verbose_name='Причина отказа')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    converted_student = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='converted_leads_as_student', verbose_name='Созданный ученик')
    converted_parent = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='converted_leads_as_parent', verbose_name='Созданный родитель')
    converted_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата конвертации')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Лид'
        verbose_name_plural = 'Лиды'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['next_contact_at']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f'{self.child_fio} · {self.phone}'

    @classmethod
    def from_participant_request(cls, participant_request, assigned_to=None):
        lead, created = cls.objects.get_or_create(
            participant_request=participant_request,
            defaults={
                'parent_fio': participant_request.parent_fio,
                'child_fio': participant_request.child_fio,
                'phone': participant_request.phone,
                'email': participant_request.email,
                'age': participant_request.age,
                'source': participant_request.source,
                'assigned_to': assigned_to,
                'status': LeadStatus.CONVERTED if participant_request.checked else LeadStatus.NEW,
            },
        )
        if created:
            lead.courses.set(participant_request.courses.all())
        return lead

    def mark_converted(self, student=None, parent=None):
        self.status = LeadStatus.CONVERTED
        self.converted_student = student
        self.converted_parent = parent
        self.converted_at = timezone.now()
        self.save(update_fields=['status', 'converted_student', 'converted_parent', 'converted_at', 'updated_at'])
