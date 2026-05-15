from django.db import models
from django.db.models import F
from django.utils import timezone
from decimal import Decimal

from accounts.models import CustomUser, UserRole
from courses.models import Courses
from schedule.models import Schedule


class Tariff(models.Model):
    """Шаблон тарифа (справочник доступных тарифов)"""
    SUBSCRIPTION_TYPE_GROUP = 'group'
    SUBSCRIPTION_TYPE_INDIVIDUAL = 'individual'

    SUBSCRIPTION_TYPE_CHOICES = [
        (SUBSCRIPTION_TYPE_GROUP, 'Групповой абонемент'),
        (SUBSCRIPTION_TYPE_INDIVIDUAL, 'Индивидуальный абонемент'),
    ]

    name = models.CharField(max_length=200, verbose_name="Название тарифа")
    course = models.ForeignKey(
        Courses,
        on_delete=models.CASCADE,
        related_name="tariffs",
        verbose_name="Курс"
    )
    lessons_count = models.IntegerField(verbose_name="Количество занятий")
    validity_days = models.IntegerField(verbose_name="Срок действия (дней)")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    subscription_type = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_TYPE_CHOICES,
        default=SUBSCRIPTION_TYPE_GROUP,
        verbose_name="Тип абонемента"
    )
    is_active = models.BooleanField(default=True, verbose_name="Доступен для покупки")
    is_trial = models.BooleanField(default=False, verbose_name="Пробный тариф")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Тариф"
        verbose_name_plural = "Тарифы"
        ordering = ['course', 'lessons_count']
    
    def __str__(self):
        trial_mark = " (Пробный)" if self.is_trial else ""
        return f"{self.name} - {self.course.name} - {self.get_subscription_type_display()}{trial_mark}"


class Subscription(models.Model):
    """Купленный тариф (подписка ученика)"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('active', 'Активный'),
        ('expired', 'Истек срок'),
        ('exhausted', 'Исчерпан'),
        ('frozen', 'Заморожен'),
        ('canceled', 'Отменен'),
    ]
    
    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name="Ученик"
    )
    parent = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='purchased_subscriptions',
        verbose_name="Родитель (покупатель)"
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name="Тариф"
    )
    
    # Параметры на момент покупки
    lessons_total = models.IntegerField(verbose_name="Всего занятий")
    lessons_used = models.IntegerField(default=0, verbose_name="Использовано занятий")
    
    # Сроки
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания")
    
    # Статус
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    # Заморозка (на будущее)
    frozen_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата заморозки")
    frozen_days = models.IntegerField(default=0, verbose_name="Дней заморожен")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.tariff.name} ({self.lessons_remaining}/{self.lessons_total})"
    
    @property
    def lessons_remaining(self):
        """Осталось занятий"""
        return self.lessons_total - self.lessons_used
    
    @property
    def is_valid(self):
        """Проверка: активна ли подписка"""
        return (
            self.status == 'active' and
            self.lessons_remaining > 0 and
            self.end_date >= timezone.now().date()
        )
    
    def deduct_lessons(self, count=1):
        """Списать занятия"""
        if self.lessons_remaining >= count:
            self.lessons_used += count
            
            # Если закончились занятия, меняем статус
            if self.lessons_remaining == 0:
                self.status = 'exhausted'
            
            self.save()
            return True
        return False
    
    def refund_lessons(self, count=1):
        """Вернуть занятия (при отмене посещения)"""
        if self.lessons_used >= count:
            self.lessons_used -= count
            
            # Если были исчерпаны, возвращаем в активные
            if self.status == 'exhausted' and self.lessons_remaining > 0:
                self.status = 'active'
            
            self.save()
            return True
        return False


class Payment(models.Model):
    """История платежей"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Наличные'),
        ('card', 'Банковская карта'),
        ('transfer', 'Банковский перевод'),
        ('online', 'Онлайн-оплата'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('completed', 'Оплачен'),
        ('failed', 'Ошибка'),
        ('refunded', 'Возврат'),
        ('canceled', 'Отменен'),
    ]
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Подписка"
    )
    parent = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Плательщик"
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name="Способ оплаты"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    # ЮKassa интеграция
    yookassa_payment_id = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        unique=True,
        verbose_name="ID платежа ЮKassa"
    )
    yookassa_payment_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="URL для оплаты"
    )
    
    # Дополнительная информация
    transaction_id = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="ID транзакции"
    )
    notes = models.TextField(blank=True, verbose_name="Примечания")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата оплаты")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Платеж #{self.id} - {self.parent.get_full_name()} - {self.amount} руб. ({self.get_status_display()})"


class LessonAttendance(models.Model):
    """Посещаемость занятий"""
    ATTENDANCE_STATUS = [
        ('present', 'Присутствовал'),
        ('absent', 'Отсутствовал'),
        ('excused', 'Уважительная причина'),
    ]
    
    LESSON_DURATION = [
        (1, '1 занятие (45 минут)'),
        (2, '2 занятия (90 минут)'),
    ]
    
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Занятие"
    )
    student = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Ученик"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendances',
        verbose_name="Подписка"
    )
    
    status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS,
        verbose_name="Статус посещения"
    )
    lessons_count = models.IntegerField(
        choices=LESSON_DURATION,
        default=2,
        verbose_name="Количество занятий"
    )
    lesson_deducted = models.BooleanField(
        default=False,
        verbose_name="Занятие списано"
    )
    
    notes = models.TextField(blank=True, verbose_name="Примечания")
    marked_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendances',
        verbose_name="Кто отметил"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Посещаемость"
        verbose_name_plural = "Посещаемость"
        unique_together = ['schedule', 'student']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.schedule} ({self.get_status_display()})"
