from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from datetime import datetime, timedelta

from django.utils import timezone

from accounts.models import UserRole
from students.models import StudentGroups
from .models import GroupScheduleTemplate, Lesson, LessonParticipant, Schedule


def get_group_teacher(group):
    """Return the teacher for a group supporting both field names used in project history."""
    return getattr(group, "teacher", None) or getattr(group, "owner", None)


def get_user_schedule(user):
    cache_key = f"user:{user.id}:schedule_ids"

    schedule_ids = cache.get(cache_key)

    if schedule_ids is None:
        if user.role == UserRole.TEACHER:
            schedule_ids = list(
                Lesson.objects
                .filter(teacher=user)
                .values_list("id", flat=True)
            )

        elif user.role == UserRole.STUDENT:
            schedule_ids = list(
                Lesson.objects
                .filter(participants__student=user)
                .distinct()
                .values_list("id", flat=True)
            )
        elif user.role == UserRole.PARENT:
            try:
                children_users = [profile.user_id for profile in user.parent_profile.students.all()]
            except Exception:
                children_users = []
            schedule_ids = list(Lesson.objects.filter(participants__student_id__in=children_users).distinct().values_list("id", flat=True))

        else:
            schedule_ids = []

        cache.set(cache_key, schedule_ids, timeout=60)

    return (
        Lesson.objects
        .filter(id__in=schedule_ids)
        .select_related("group", "group__course", "teacher", "course")
        .prefetch_related("participants", "participants__student")
    )


class LessonService:
    @staticmethod
    @transaction.atomic
    def create_lesson(*, lesson_type, starts_at, ends_at, teacher, course=None, group=None, participants=None, created_by=None):
        if group and course is None:
            course = group.course
        lesson = Lesson.objects.create(
            lesson_type=lesson_type,
            starts_at=starts_at,
            ends_at=ends_at,
            teacher=teacher,
            course=course,
            group=group,
            created_by=created_by,
        )
        lesson.full_clean()
        lesson.save()
        if group and not participants:
            LessonService.create_participants_for_group_lesson(lesson)
        for student in participants or []:
            LessonService.add_participant(lesson, student)
        return lesson

    @staticmethod
    def create_group_lesson(group, starts_at, ends_at, teacher=None, created_by=None):
        return LessonService.create_lesson(lesson_type=Lesson.LessonType.GROUP, group=group, course=group.course, teacher=teacher or group.teacher, starts_at=starts_at, ends_at=ends_at, created_by=created_by)

    @staticmethod
    def create_individual_lesson(student, course, teacher, starts_at, ends_at, created_by=None):
        return LessonService.create_lesson(lesson_type=Lesson.LessonType.INDIVIDUAL, course=course, teacher=teacher, starts_at=starts_at, ends_at=ends_at, participants=[student], created_by=created_by)

    @staticmethod
    def create_participants_for_group_lesson(lesson):
        created = []
        for membership in StudentGroups.objects.select_related('student').filter(group=lesson.group):
            participant, was_created = LessonParticipant.objects.get_or_create(lesson=lesson, student=membership.student)
            if was_created:
                created.append(participant)
        return created

    @staticmethod
    def add_participant(lesson, student, subscription=None, order_item=None, lessons_to_charge=0):
        participant, _ = LessonParticipant.objects.get_or_create(
            lesson=lesson,
            student=student,
            defaults={'subscription': subscription, 'order_item': order_item, 'lessons_to_charge': lessons_to_charge},
        )
        return participant

    @staticmethod
    def cancel_lesson(lesson, reason, canceled_by=None):
        lesson.status = Lesson.Status.CANCELLED
        lesson.cancel_reason = reason or ''
        lesson.save(update_fields=['status', 'cancel_reason', 'updated_at'])
        lesson.participants.update(attendance_status=LessonParticipant.AttendanceStatus.CANCELED)
        return lesson

    @staticmethod
    def reschedule_lesson(lesson, starts_at, ends_at, reason, changed_by=None):
        if not lesson.original_starts_at:
            lesson.original_starts_at = lesson.starts_at
            lesson.original_ends_at = lesson.ends_at
        lesson.starts_at = starts_at
        lesson.ends_at = ends_at
        lesson.reschedule_reason = reason or ''
        lesson.status = Lesson.Status.RESCHEDULED
        lesson.save()
        return lesson

    @staticmethod
    def mark_participant_attendance(participant, status, lessons_to_charge=0, marked_by=None, notes=''):
        from subscriptions.services import SubscriptionUsageService
        participant.attendance_status = status
        participant.lessons_to_charge = int(lessons_to_charge or participant.lessons_to_charge or 0)
        participant.marked_by = marked_by
        participant.marked_at = timezone.now()
        participant.notes = notes or ''
        participant.save(update_fields=['attendance_status', 'lessons_to_charge', 'marked_by', 'marked_at', 'notes', 'updated_at'])
        if status in [LessonParticipant.AttendanceStatus.PRESENT, LessonParticipant.AttendanceStatus.ABSENT_CHARGED] and not participant.lesson.is_single:
            SubscriptionUsageService.charge_participant(participant, participant.lessons_to_charge or 1, charged_by=marked_by)
        return participant

    @staticmethod
    def cancel_participant_attendance(participant, canceled_by=None):
        from subscriptions.services import SubscriptionUsageService
        SubscriptionUsageService.refund_participant_charge(participant, refunded_by=canceled_by)
        participant.attendance_status = LessonParticipant.AttendanceStatus.PLANNED
        participant.lessons_to_charge = 0
        participant.marked_by = None
        participant.marked_at = None
        participant.notes = ''
        participant.save(update_fields=['attendance_status', 'lessons_to_charge', 'marked_by', 'marked_at', 'notes', 'updated_at'])
        return participant


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

            end_dt = timezone.make_aware(datetime.combine(current_date, end_time))
            lesson, was_created = Lesson.objects.get_or_create(
                group=template.group,
                starts_at=start_dt,
                defaults={
                    "ends_at": end_dt,
                    "teacher": teacher,
                    "course": template.group.course,
                    "lesson_type": Lesson.LessonType.GROUP,
                    "status": "scheduled",
                },
            )

            if was_created:
                LessonService.create_participants_for_group_lesson(lesson)
                created.append(lesson)

        current_date += timedelta(days=1)

    return created
