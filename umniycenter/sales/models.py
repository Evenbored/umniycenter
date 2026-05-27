from django.db import models
from django.utils import timezone

from accounts.models import CustomUser, LeadSource, UserRole
from courses.models import Courses
from main.models import ParticipantRequest
from schedule.models import Lesson, Schedule
from subscriptions.models import Payment, Subscription, Tariff


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


class OrderStatus(models.TextChoices):
    DRAFT = 'draft', 'Черновик'
    PENDING = 'pending', 'Ожидает оплаты'
    PENDING_PAYMENT = 'pending_payment', 'Ожидает оплаты'
    PARTIALLY_PAID = 'partially_paid', 'Частично оплачен'
    PAID = 'paid', 'Оплачен'
    CANCELED = 'canceled', 'Отменен'
    REFUNDED = 'refunded', 'Возврат'


class OrderItemType(models.TextChoices):
    SUBSCRIPTION = 'subscription', 'Абонемент'
    SINGLE_GROUP = 'single_group', 'Групповое разовое занятие'
    SINGLE_INDIVIDUAL = 'single_individual', 'Индивидуальное разовое занятие'
    PRODUCT = 'product', 'Товар'
    RENT = 'rent', 'Аренда'
    ACCOUNT_TOPUP = 'account_topup', 'Пополнение лицевого счета'


class Order(models.Model):
    parent = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_orders', verbose_name='Покупатель')
    student = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_sales_orders', verbose_name='Ученик')
    status = models.CharField(max_length=24, choices=OrderStatus.choices, default=OrderStatus.PENDING, verbose_name='Статус')
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='legacy_order', verbose_name='Связанный платеж абонемента')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Сумма')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Оплачено')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата оплаты')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_sales_orders', verbose_name='Кто создал')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Заказ/продажа'
        verbose_name_plural = 'Заказы/продажи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['paid_at']),
        ]

    def __str__(self):
        return f'Заказ #{self.id} · {self.total_amount} ₽'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    item_type = models.CharField(max_length=32, choices=OrderItemType.choices, verbose_name='Тип позиции')
    title = models.CharField(max_length=255, verbose_name='Название')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Цена за единицу')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    course = models.ForeignKey(Courses, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Курс')
    tariff = models.ForeignKey(Tariff, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Тариф')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Абонемент')
    schedule = models.ForeignKey(Schedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Занятие')
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Занятие (new)')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Дополнительные данные')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказов'
        ordering = ['id']
        indexes = [
            models.Index(fields=['item_type', 'created_at']),
            models.Index(fields=['schedule']),
            models.Index(fields=['lesson']),
            models.Index(fields=['subscription']),
        ]

    def __str__(self):
        return f'{self.get_item_type_display()}: {self.title}'
