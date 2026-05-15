from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models
from accounts.models import CustomUser, UserRole
from groups.models import SchoolGroups

class Schedule(models.Model):
    LESSON_TYPE_REGULAR = 'regular'
    LESSON_TYPE_SINGLE = 'single'

    LESSON_TYPE_CHOICES = [
        (LESSON_TYPE_REGULAR, 'Постоянное занятие'),
        (LESSON_TYPE_SINGLE, 'Разовое занятие'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('completed', 'Прошло'),
        ('cancelled', 'Отменено'),
        ('rescheduled', 'Перенесено'),
    ]

    group = models.ForeignKey(SchoolGroups,
                              on_delete=models.CASCADE, null=True, blank=True, verbose_name="Группа")
    student = models.ForeignKey(CustomUser,
                                on_delete=models.CASCADE, null=True, blank=True, related_name="individual_schedules", verbose_name="Ученик")
    students = models.ManyToManyField(CustomUser, blank=True, related_name="group_schedules", verbose_name="Ученики занятия")
    course = models.ForeignKey('courses.Courses',
                               on_delete=models.CASCADE, null=True, blank=True, verbose_name="Курс")
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, default=LESSON_TYPE_REGULAR, verbose_name="Тип занятия")
    is_single = models.BooleanField(default=False, verbose_name="Разовое занятие")
    classdateStart = models.DateTimeField(default=timezone.now, verbose_name="Дата и время начала")
    classdateEnd = models.TimeField(default=timezone.now, verbose_name="Дата и время окончания")
    
    teacher = models.ForeignKey(CustomUser,
                                on_delete=models.CASCADE, verbose_name="Преподаватель")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled', verbose_name="Статус")
    original_classdateStart = models.DateTimeField(null=True, blank=True, verbose_name="Изначальная дата и время начала")
    original_classdateEnd = models.TimeField(null=True, blank=True, verbose_name="Изначальное время окончания")
    cancel_reason = models.CharField(max_length=255, blank=True, verbose_name="Причина отмены")
    reschedule_reason = models.CharField(max_length=255, blank=True, verbose_name="Причина переноса")

    class Meta:
        verbose_name = ("Расписание")
        verbose_name_plural = ("Расписание")

    def clean(self):
        if not self.lesson_type:
            self.lesson_type = self.LESSON_TYPE_REGULAR

        if self.lesson_type == 'group':
            self.lesson_type = self.LESSON_TYPE_REGULAR
        elif self.lesson_type == 'individual':
            self.lesson_type = self.LESSON_TYPE_REGULAR

        if self.group and not self.course:
            self.course = self.group.course

        if self.teacher and self.teacher.role != UserRole.TEACHER:
            raise ValidationError("Вести занятие может быть только преподаватель")

        if self.group:
            if not self.group:
                raise ValidationError("Для группового занятия нужно выбрать группу")
            self.student = None
            self.course = self.group.course
        else:
            if not self.student:
                raise ValidationError("Для занятия без группы нужно выбрать ученика")
            if self.student.role != UserRole.STUDENT:
                raise ValidationError("В занятие можно записать только ученика")
            if not self.course:
                raise ValidationError("Для занятия без группы нужно выбрать курс")
            self.group = None

        self.is_single = self.lesson_type == self.LESSON_TYPE_SINGLE

    @property
    def title(self):
        if self.group:
            return str(self.group)
        if self.student:
            prefix = 'Разовое' if self.is_single or self.lesson_type == self.LESSON_TYPE_SINGLE else 'Постоянное'
            return f"{prefix}: {self.student.get_full_name() or self.student.username}"
        return 'Занятие'

    @property
    def course_name(self):
        if self.group and self.group.course:
            return self.group.course.name
        if self.course:
            return self.course.name
        return ''

    @property
    def is_past(self):
        """Проверяет, прошло ли занятие"""
        from datetime import datetime
        end_datetime = datetime.combine(self.classdateStart.date(), self.classdateEnd)
        end_datetime_aware = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
        return end_datetime_aware < timezone.now()

    @property
    def actual_status(self):
        """Возвращает актуальный статус с учетом времени"""
        # Отмененные занятия всегда остаются отмененными
        if self.status == 'cancelled':
            return self.status
        
        # Проверяем, прошло ли занятие (даже если оно было перенесено)
        if self.is_past:
            return 'completed'
        
        # Если занятие перенесено и еще не прошло
        if self.status == 'rescheduled':
            return self.status
        
        return 'scheduled'

    def __str__(self):
        return f'{self.title} - {self.classdateStart} - {self.classdateEnd} - {self.teacher}'


class GroupScheduleTemplate(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]

    LESSON_DURATION_CHOICES = [
        (1, '1 занятие (45 минут)'),
        (2, '2 занятия (90 минут)'),
    ]

    group = models.ForeignKey(SchoolGroups, on_delete=models.CASCADE, related_name="schedule_templates", verbose_name="Группа")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES, verbose_name="День недели")
    start_time = models.TimeField(verbose_name="Время начала")
    lessons_count = models.PositiveSmallIntegerField(choices=LESSON_DURATION_CHOICES, default=2, verbose_name="Количество занятий")
    is_active = models.BooleanField(default=True, verbose_name="Активный шаблон")

    class Meta:
        verbose_name = "Шаблон расписания группы"
        verbose_name_plural = "Шаблоны расписания групп"
        constraints = [
            models.UniqueConstraint(fields=["group", "weekday", "start_time"], name="unique_group_schedule_template"),
        ]
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.group} · {self.get_weekday_display()} {self.start_time}"
