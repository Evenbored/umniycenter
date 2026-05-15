from django.core.validators import RegexValidator
from django.db import models
from django.utils.html import strip_tags

from courses.models import Courses
from accounts.models import LeadSource


class ParticipantRequest(models.Model):
    parent_fio = models.CharField(max_length=150, verbose_name="ФИО родителя")
    child_fio = models.CharField(max_length=150, verbose_name="ФИО ребенка")
    phone = models.CharField(
        max_length=20,
        verbose_name="Телефон",
        default='+70000000000',
        validators=[
            RegexValidator(
                regex=r'^\+7\d{10}$',
                message='Номер телефона должен начинаться с +7 и содержать 10 цифр после него (например: +79001234567)'
            )
        ]
    )
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Почта (необязательно)")
    age = models.CharField(max_length=3, verbose_name="Возраст ребенка")
    courses = models.ManyToManyField(Courses, verbose_name="Выбранные курсы", related_name="participant_requests")
    source = models.CharField(
        max_length=20,
        choices=LeadSource.choices,
        blank=True,
        null=True,
        verbose_name="Как узнали о центре"
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время обращения")
    checked = models.BooleanField(default=False, verbose_name="Обработана")
    
    class Meta:
        ordering = ('-created',)
        verbose_name = ("Заявку")
        verbose_name_plural = ("Заявки")

    def __str__(self):
        return f"Заявка {self.id}"
    
    def save(self, *args, **kwargs):
        """Очистка текстовых полей от HTML-тегов перед сохранением"""
        self.parent_fio = strip_tags(self.parent_fio)
        self.child_fio = strip_tags(self.child_fio)
        self.age = strip_tags(str(self.age))
        super().save(*args, **kwargs)
    
    def get_courses_display(self):
        return ", ".join([course.name for course in self.courses.all()])

