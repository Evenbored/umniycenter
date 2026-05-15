from django.db import models
from django.conf import settings
from django.utils import timezone
from accounts.models import UserRole

class TicketCategory(models.TextChoices):
    """Предопределенные категории обращений"""
    PAYMENT = 'payment', 'Вопрос по оплате'
    SCHEDULE = 'schedule', 'Вопрос по расписанию'
    PROGRESS = 'progress', 'Успеваемость ребенка'
    ABSENCE = 'absence', 'Пропуск занятий'
    TEACHER = 'teacher', 'Вопрос по преподавателю'
    TECHNICAL = 'technical', 'Технический вопрос'
    OTHER = 'other', 'Другое'

class TicketStatus(models.TextChoices):
    """Статусы обращения"""
    OPEN = 'open', 'Открыто'
    IN_PROGRESS = 'in_progress', 'В работе'
    WAITING_PARENT = 'waiting_parent', 'Ожидает ответа родителя'
    CLOSED = 'closed', 'Закрыто'

class Ticket(models.Model):
    """
    Обращение родителя к администрации.
    Родитель может иметь несколько тикетов (активных и закрытых),
    но в UI видит их как один непрерывный чат.
    """
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets',
        limit_choices_to={'role': UserRole.PARENT},
        verbose_name="Родитель"
    )
    
    assigned_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        limit_choices_to={'role': UserRole.ADMIN},
        verbose_name="Ответственный администратор"
    )
    
    # Тема обращения (опционально, может определяться автоматически из первого сообщения)
    category = models.CharField(
        max_length=20,
        choices=TicketCategory.choices,
        default=TicketCategory.OTHER,
        verbose_name="Категория"
    )
    
    # Краткая тема (первые слова первого сообщения или заданная родителем)
    subject = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Тема"
    )
    
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        verbose_name="Статус"
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено"
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последнее сообщение"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Закрыто"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_tickets',
        verbose_name="Закрыл"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Обращение"
        verbose_name_plural = "Обращения"
        indexes = [
            models.Index(fields=['parent', '-created_at']),
            models.Index(fields=['assigned_admin', 'status', '-created_at']),
            models.Index(fields=['status', '-last_message_at']),
            models.Index(fields=['-last_message_at']),
        ]
    
    def __str__(self):
        subject = self.subject or self.get_category_display()
        return f"#{self.id}: {subject} - {self.parent.get_full_name()}"
    
    def assign_to_admin(self, admin):
        """Назначить обращение администратору"""
        if admin.role != UserRole.ADMIN:
            raise ValueError("Только администратор может быть назначен на обращение")
        
        self.assigned_admin = admin
        if self.status == TicketStatus.OPEN:
            self.status = TicketStatus.IN_PROGRESS
        self.save(update_fields=['assigned_admin', 'status', 'updated_at'])
    
    def close(self, admin):
        """Закрыть обращение (только администратор)"""
        if admin.role != UserRole.ADMIN:
            raise ValueError("Только администратор может закрыть обращение")
        
        self.status = TicketStatus.CLOSED
        self.closed_at = timezone.now()
        self.closed_by = admin
        self.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
    
    @property
    def is_active(self):
        """Проверка, активно ли обращение"""
        return self.status in [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING_PARENT
        ]
    
    @property
    def unread_count_for_parent(self):
        """Количество непрочитанных сообщений для родителя"""
        return self.messages.filter(
            sender__role=UserRole.ADMIN,
            is_read=False
        ).count()
    
    @property
    def unread_count_for_admin(self):
        """Количество непрочитанных сообщений для администратора"""
        return self.messages.filter(
            sender__role=UserRole.PARENT,
            is_read=False
        ).count()
    
    @classmethod
    def get_or_create_active_ticket(cls, parent):
        """
        Получить активный тикет родителя или создать новый.
        Используется когда родитель отправляет сообщение.
        Использует select_for_update для предотвращения race condition.
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Ищем активный тикет с блокировкой
            active_ticket = cls.objects.select_for_update().filter(
                parent=parent,
                status__in=[
                    TicketStatus.OPEN,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.WAITING_PARENT
                ]
            ).first()
            
            if active_ticket:
                return active_ticket, False
            
            # Создаем новый тикет
            new_ticket = cls.objects.create(
                parent=parent,
                status=TicketStatus.OPEN
            )
            return new_ticket, True
    
    @classmethod
    def get_parent_chat_history(cls, parent):
        """
        Получить всю историю чата родителя (все тикеты с сообщениями).
        Используется для отображения единого окна чата.
        """
        return cls.objects.filter(parent=parent).prefetch_related(
            'messages',
            'messages__sender'
        ).order_by('created_at')

class Message(models.Model):
    """Сообщение в обращении"""
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name="Обращение"
    )
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name="Отправитель"
    )
    
    content = models.TextField(
        verbose_name="Содержание"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Отправлено"
    )
    
    is_read = models.BooleanField(
        default=False,
        verbose_name="Прочитано"
    )
    
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время прочтения"
    )
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['ticket', 'is_read']),
            models.Index(fields=['sender', '-created_at']),
        ]
    
    def __str__(self):
        return f"Сообщение от {self.sender.get_full_name()} в {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        if is_new:
            # Обновляем время последнего сообщения в обращении
            self.ticket.last_message_at = self.created_at
            
            # Если это первое сообщение в тикете, устанавливаем тему
            if self.ticket.messages.count() == 1 and not self.ticket.subject:
                # Берем первые 50 символов сообщения как тему
                self.ticket.subject = self.content[:50] + ('...' if len(self.content) > 50 else '')
            
            # Если это первое сообщение от админа, назначаем его ответственным
            if self.sender.role == UserRole.ADMIN:
                if not self.ticket.assigned_admin:
                    self.ticket.assigned_admin = self.sender
                
                # Меняем статус на "Ожидает ответа родителя"
                if self.ticket.status != TicketStatus.CLOSED:
                    self.ticket.status = TicketStatus.WAITING_PARENT
            
            # Если родитель отвечает
            elif self.sender.role == UserRole.PARENT:
                if self.ticket.status == TicketStatus.WAITING_PARENT:
                    self.ticket.status = TicketStatus.IN_PROGRESS
            
            self.ticket.save(update_fields=['last_message_at', 'assigned_admin', 'status', 'subject', 'updated_at'])
    
    def mark_as_read(self):
        """Отметить сообщение как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])