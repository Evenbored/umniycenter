from django.core.cache import cache
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta

from django.utils import timezone

from accounts.models import UserRole
from students.models import StudentGroups
from .models import GroupScheduleTemplate, Schedule


def get_group_teacher(group):
    """Return the teacher for a group supporting both field names used in project history."""
    return getattr(group, "teacher", None) or getattr(group, "owner", None)


def get_user_schedule(user):
    cache_key = f"user:{user.id}:schedule_ids"

    schedule_ids = cache.get(cache_key)

    if schedule_ids is None:
        if user.role == UserRole.TEACHER:
            schedule_ids = list(
                Schedule.objects
                .filter(teacher=user)
                .values_list("id", flat=True)
            )

        elif user.role == UserRole.STUDENT:
            student_group_ids = list(
                StudentGroups.objects.filter(student=user).values_list("group_id", flat=True)
            )
            schedule_ids = list(
                Schedule.objects
                .filter(group_id__in=student_group_ids)
                .values_list("id", flat=True)
            ) + list(
                Schedule.objects
                .filter(student=user)
                .values_list("id", flat=True)
            )

        else:
            schedule_ids = []

        cache.set(cache_key, schedule_ids, timeout=60)

    return (
        Schedule.objects
        .filter(id__in=schedule_ids)
        .select_related("group", "group__course", "teacher", "student", "course")
    )


def get_lesson_end_time(start_time, lessons_count):
    """Вычисляет время окончания занятия"""
    from datetime import datetime, timedelta
    
    lesson_minutes = 45 * int(lessons_count)
    # Используем произвольную дату для вычисления времени
    dummy_date = datetime(2000, 1, 1)
    start_dt = datetime.combine(dummy_date, start_time)
    end_dt = start_dt + timedelta(minutes=lesson_minutes)
    return end_dt.time()


def generate_schedule_for_range(date_from, date_to, group_id=None):
    templates = GroupScheduleTemplate.objects.filter(is_active=True).select_related("group", "group__teacher")

    if group_id:
        templates = templates.filter(group_id=group_id)

    created = []
    current_date = date_from
    now = timezone.now()

    while current_date <= date_to:
        day_templates = templates.filter(weekday=current_date.weekday())

        for template in day_templates:
            teacher = get_group_teacher(template.group)
            if not teacher:
                raise ValidationError(f"У группы {template.group} не указан преподаватель")

            start_dt = timezone.make_aware(datetime.combine(current_date, template.start_time))
            
            # Пропускаем занятия, которые уже прошли
            if start_dt < now:
                continue
            
            end_time = get_lesson_end_time(template.start_time, template.lessons_count)

            lesson, was_created = Schedule.objects.get_or_create(
                group=template.group,
                classdateStart=start_dt,
                defaults={
                    "classdateEnd": end_time,
                    "teacher": teacher,
                    "course": template.group.course,
                    "status": "scheduled",
                },
            )

            if was_created:
                created.append(lesson)

        current_date += timedelta(days=1)

    return created
