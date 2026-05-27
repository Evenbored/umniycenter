from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import models
from accounts.models import CustomUser, UserRole
from groups.models import SchoolGroups


class Lesson(models.Model):
    class LessonType(models.TextChoices):
        GROUP = 'group', 'Групповое'
        INDIVIDUAL = 'individual', 'Индивидуальное'
        SINGLE_GROUP = 'single_group', 'Разовое групповое'
        SINGLE_INDIVIDUAL = 'single_individual', 'Разовое индивидуальное'
        TRIAL_GROUP = 'trial_group', 'Пробное групповое'
        TRIAL_INDIVIDUAL = 'trial_individual', 'Пробное индивидуальное'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Запланировано'
        COMPLETED = 'completed', 'Проведено'
        CANCELLED = 'cancelled', 'Отменено'
        RESCHEDULED = 'rescheduled', 'Перенесено'

    GROUP_TYPES = {LessonType.GROUP, LessonType.SINGLE_GROUP, LessonType.TRIAL_GROUP}
    INDIVIDUAL_TYPES = {LessonType.INDIVIDUAL, LessonType.SINGLE_INDIVIDUAL, LessonType.TRIAL_INDIVIDUAL}

    group = models.ForeignKey(SchoolGroups, on_delete=models.CASCADE, null=True, blank=True, related_name='lessons', verbose_name='Группа')
    course = models.ForeignKey('courses.Courses', on_delete=models.PROTECT, related_name='lessons', verbose_name='Курс')
    teacher = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='teacher_lessons', verbose_name='Преподаватель')
    lesson_type = models.CharField(max_length=32, choices=LessonType.choices, verbose_name='Тип занятия')
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SCHEDULED, verbose_name='Статус')
    starts_at = models.DateTimeField(db_index=True, verbose_name='Начало')
    ends_at = models.DateTimeField(db_index=True, verbose_name='Окончание')
    original_starts_at = models.DateTimeField(null=True, blank=True, verbose_name='Изначальное начало')
    original_ends_at = models.DateTimeField(null=True, blank=True, verbose_name='Изначальное окончание')
    cancel_reason = models.CharField(max_length=255, blank=True, verbose_name='Причина отмены')
    reschedule_reason = models.CharField(max_length=255, blank=True, verbose_name='Причина переноса')
    legacy_schedule_id = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name='Legacy Schedule ID')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_lessons', verbose_name='Кто создал')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Занятие'
        verbose_name_plural = 'Занятия'
        ordering = ['starts_at']
        constraints = [
            models.CheckConstraint(check=models.Q(ends_at__gt=models.F('starts_at')), name='lesson_ends_after_starts'),
        ]
        indexes = [
            models.Index(fields=['starts_at']),
            models.Index(fields=['status', 'starts_at']),
            models.Index(fields=['teacher', 'starts_at']),
            models.Index(fields=['group', 'starts_at']),
            models.Index(fields=['course', 'starts_at']),
        ]

    def clean(self):
        if self.teacher and self.teacher.role != UserRole.TEACHER:
            raise ValidationError('Вести занятие может быть только преподаватель')
        if self.group:
            self.course = self.group.course
        if self.lesson_type in self.GROUP_TYPES and not self.group:
            raise ValidationError('Для группового занятия нужно выбрать группу')
        if self.lesson_type in self.INDIVIDUAL_TYPES and self.group:
            raise ValidationError('Для индивидуального занятия группа должна быть пустой')
        if not self.course:
            raise ValidationError('Для занятия нужно выбрать курс')
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError('Время окончания должно быть позже времени начала')

    @property
    def title(self):
        if self.group:
            return str(self.group)
        return f'{self.get_lesson_type_display()} · {self.course}'

    @property
    def course_name(self):
        return self.course.name if self.course else ''

    @property
    def is_past(self):
        return bool(self.ends_at and self.ends_at < timezone.now())

    @property
    def actual_status(self):
        if self.status == self.Status.CANCELLED:
            return self.status
        if self.is_past:
            return self.Status.COMPLETED
        return self.status

    @property
    def is_single(self):
        return self.lesson_type in {self.LessonType.SINGLE_GROUP, self.LessonType.SINGLE_INDIVIDUAL}

    @property
    def classdateStart(self):
        return self.starts_at

    @classdateStart.setter
    def classdateStart(self, value):
        self.starts_at = value

    @property
    def classdateEnd(self):
        return self.ends_at.time() if self.ends_at else None

    @classdateEnd.setter
    def classdateEnd(self, value):
        from datetime import datetime
        if value and self.starts_at:
            end_dt = datetime.combine(self.starts_at.date(), value)
            self.ends_at = timezone.make_aware(end_dt) if timezone.is_naive(end_dt) else end_dt

    @property
    def original_classdateStart(self):
        return self.original_starts_at

    @original_classdateStart.setter
    def original_classdateStart(self, value):
        self.original_starts_at = value

    @property
    def original_classdateEnd(self):
        return self.original_ends_at.time() if self.original_ends_at else None

    @original_classdateEnd.setter
    def original_classdateEnd(self, value):
        from datetime import datetime
        if value and self.original_starts_at:
            end_dt = datetime.combine(self.original_starts_at.date(), value)
            self.original_ends_at = timezone.make_aware(end_dt) if timezone.is_naive(end_dt) else end_dt

    @property
    def student(self):
        participant = getattr(self, '_first_participant', None)
        if participant:
            return participant.student
        try:
            participant = self.participants.select_related('student').first()
            return participant.student if participant else None
        except Exception:
            return None

    @property
    def student_id(self):
        student = self.student
        return student.id if student else None

    def __str__(self):
        return f'{self.title} - {self.starts_at} - {self.ends_at} - {self.teacher}'


class LessonParticipant(models.Model):
    class LegacyCompatibleManager(models.Manager):
        def _rewrite_kwargs(self, kwargs, for_create=False):
            kwargs = dict(kwargs)
            if 'schedule' in kwargs:
                kwargs['lesson'] = kwargs.pop('schedule')
            if 'schedule_id' in kwargs:
                kwargs['lesson_id'] = kwargs.pop('schedule_id')
            if 'lessons_count' in kwargs:
                kwargs['lessons_to_charge'] = kwargs.pop('lessons_count')
            if 'lesson_deducted' in kwargs:
                kwargs['lessons_charged'] = kwargs.pop('lesson_deducted')
            if 'status' in kwargs:
                value = kwargs.pop('status')
                if value == 'absent':
                    kwargs['attendance_status'] = LessonParticipant.AttendanceStatus.ABSENT_NOT_CHARGED
                else:
                    kwargs['attendance_status'] = value
            return kwargs

        def create(self, **kwargs):
            return super().create(**self._rewrite_kwargs(kwargs, for_create=True))

        def filter(self, *args, **kwargs):
            if kwargs.get('status') == 'absent':
                kwargs = dict(kwargs)
                kwargs.pop('status')
                kwargs['attendance_status__in'] = [
                    LessonParticipant.AttendanceStatus.ABSENT_CHARGED,
                    LessonParticipant.AttendanceStatus.ABSENT_NOT_CHARGED,
                ]
            return super().filter(*args, **self._rewrite_kwargs(kwargs))

        def get(self, *args, **kwargs):
            return super().get(*args, **self._rewrite_kwargs(kwargs))

        def get_or_create(self, defaults=None, **kwargs):
            defaults = self._rewrite_kwargs(defaults or {}, for_create=True)
            return super().get_or_create(defaults=defaults, **self._rewrite_kwargs(kwargs))

        def update_or_create(self, defaults=None, **kwargs):
            defaults = self._rewrite_kwargs(defaults or {}, for_create=True)
            return super().update_or_create(defaults=defaults, **self._rewrite_kwargs(kwargs))

    class AttendanceStatus(models.TextChoices):
        PLANNED = 'planned', 'Запланирован'
        PRESENT = 'present', 'Присутствовал'
        ABSENT_CHARGED = 'absent_charged', 'Отсутствовал, списано'
        ABSENT_NOT_CHARGED = 'absent_not_charged', 'Отсутствовал, не списано'
        EXCUSED = 'excused', 'Уважительная причина'
        CANCELED = 'canceled', 'Отменено'

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='participants', verbose_name='Занятие')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='lesson_participations', verbose_name='Ученик')
    subscription = models.ForeignKey('subscriptions.Subscription', on_delete=models.SET_NULL, null=True, blank=True, related_name='lesson_participations', verbose_name='Абонемент')
    order_item = models.ForeignKey('sales.OrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='lesson_participations', verbose_name='Позиция заказа')
    attendance_status = models.CharField(max_length=32, choices=AttendanceStatus.choices, default=AttendanceStatus.PLANNED, verbose_name='Статус посещаемости')
    lessons_to_charge = models.PositiveSmallIntegerField(default=0, verbose_name='Списать занятий')
    lessons_charged = models.BooleanField(default=False, verbose_name='Занятия списаны')
    charged_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата списания')
    charged_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='charged_lesson_participants', verbose_name='Кто списал')
    marked_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='marked_lesson_participants', verbose_name='Кто отметил')
    marked_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отметки')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LegacyCompatibleManager()

    class Meta:
        verbose_name = 'Участник занятия'
        verbose_name_plural = 'Участники занятий'
        constraints = [
            models.UniqueConstraint(fields=['lesson', 'student'], name='unique_student_per_lesson'),
        ]
        indexes = [
            models.Index(fields=['student', '-created_at']),
            models.Index(fields=['lesson', 'attendance_status']),
            models.Index(fields=['subscription']),
            models.Index(fields=['order_item']),
        ]

    def clean(self):
        if self.student and self.student.role != UserRole.STUDENT:
            raise ValidationError('Участником занятия может быть только ученик')
        if self.subscription_id:
            if self.subscription.student_id != self.student_id:
                raise ValidationError('Абонемент принадлежит другому ученику')
            if self.subscription.tariff.course_id != self.lesson.course_id:
                raise ValidationError('Курс абонемента не соответствует курсу занятия')

    def __str__(self):
        return f'{self.student} · {self.lesson}'

    # Backward-compatible aliases for old tests/templates that used
    # subscriptions.LessonAttendance naming.
    @property
    def schedule(self):
        return self.lesson

    @property
    def status(self):
        if self.attendance_status in [self.AttendanceStatus.ABSENT_CHARGED, self.AttendanceStatus.ABSENT_NOT_CHARGED]:
            return 'absent'
        return self.attendance_status

    @status.setter
    def status(self, value):
        self.attendance_status = self.AttendanceStatus.ABSENT_NOT_CHARGED if value == 'absent' else value

    @property
    def lessons_count(self):
        return self.lessons_to_charge

    @lessons_count.setter
    def lessons_count(self, value):
        self.lessons_to_charge = value

    @property
    def lesson_deducted(self):
        return self.lessons_charged

    @lesson_deducted.setter
    def lesson_deducted(self, value):
        self.lessons_charged = value

    def get_status_display(self):
        return self.get_attendance_status_display()

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
