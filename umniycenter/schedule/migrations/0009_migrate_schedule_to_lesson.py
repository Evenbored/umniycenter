from datetime import datetime, timedelta

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def combine_end(starts_at, end_time):
    end_dt = datetime.combine(starts_at.date(), end_time)
    end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone()) if timezone.is_naive(end_dt) else end_dt
    if end_dt <= starts_at:
        # Legacy Schedule.classdateEnd was a TimeField and some rows contain
        # an invalid/default time earlier than classdateStart. New Lesson has
        # a DB check constraint ends_at > starts_at, so normalize such rows to
        # a minimal valid 45-minute lesson instead of aborting the migration.
        end_dt = starts_at + timedelta(minutes=45)
    return end_dt


def migrate_schedule_to_lesson(apps, schema_editor):
    Schedule = apps.get_model('schedule', 'Schedule')
    Lesson = apps.get_model('schedule', 'Lesson')
    LessonParticipant = apps.get_model('schedule', 'LessonParticipant')
    StudentGroups = apps.get_model('students', 'StudentGroups')
    LessonAttendance = apps.get_model('subscriptions', 'LessonAttendance')

    for old in Schedule.objects.select_related('group', 'course', 'teacher').prefetch_related('students').all().iterator(chunk_size=500):
        group_id = old.group_id
        course_id = old.group.course_id if old.group_id else old.course_id
        if not course_id or not old.teacher_id:
            continue
        if old.is_single and group_id:
            lesson_type = 'single_group'
        elif old.is_single and not group_id:
            lesson_type = 'single_individual'
        elif group_id:
            lesson_type = 'group'
        else:
            lesson_type = 'individual'
        lesson, _ = Lesson.objects.get_or_create(
            legacy_schedule_id=old.id,
            defaults={
                'group_id': group_id,
                'course_id': course_id,
                'teacher_id': old.teacher_id,
                'lesson_type': lesson_type,
                'status': old.status,
                'starts_at': old.classdateStart,
                'ends_at': combine_end(old.classdateStart, old.classdateEnd),
                'original_starts_at': old.original_classdateStart,
                'original_ends_at': combine_end(old.original_classdateStart, old.original_classdateEnd) if old.original_classdateStart and old.original_classdateEnd else None,
                'cancel_reason': old.cancel_reason,
                'reschedule_reason': old.reschedule_reason,
            },
        )

        added_students = set()
        for attendance in LessonAttendance.objects.filter(schedule_id=old.id).select_related('subscription'):
            if attendance.status == 'present':
                status = 'present'
            elif attendance.status == 'excused':
                status = 'excused'
            elif attendance.lesson_deducted:
                status = 'absent_charged'
            else:
                status = 'absent_not_charged'
            LessonParticipant.objects.update_or_create(
                lesson=lesson,
                student_id=attendance.student_id,
                defaults={
                    'subscription_id': attendance.subscription_id,
                    'attendance_status': status,
                    'lessons_to_charge': attendance.lessons_count,
                    'lessons_charged': attendance.lesson_deducted,
                    'charged_at': attendance.updated_at if attendance.lesson_deducted else None,
                    'charged_by_id': attendance.marked_by_id if attendance.lesson_deducted else None,
                    'marked_by_id': attendance.marked_by_id,
                    'marked_at': attendance.updated_at,
                    'notes': attendance.notes,
                },
            )
            added_students.add(attendance.student_id)

        for student_id in old.students.values_list('id', flat=True):
            if student_id not in added_students:
                LessonParticipant.objects.get_or_create(lesson=lesson, student_id=student_id)
                added_students.add(student_id)

        if old.group_id and not added_students:
            for student_id in StudentGroups.objects.filter(group_id=old.group_id).values_list('student_id', flat=True):
                LessonParticipant.objects.get_or_create(lesson=lesson, student_id=student_id)
                added_students.add(student_id)

        if old.student_id and old.student_id not in added_students:
            LessonParticipant.objects.get_or_create(lesson=lesson, student_id=old.student_id)


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0008_lessonparticipant_billing_links'),
        ('subscriptions', '0007_order_payment_refund_new_lesson_log'),
        ('students', '0002_dedupe_studentgroups_unique_constraint'),
    ]

    operations = [
        migrations.RunPython(migrate_schedule_to_lesson, migrations.RunPython.noop),
    ]
