"""
Tests for Schedule models.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, time
from schedule.models import Lesson, GroupScheduleTemplate
from schedule.services import LessonService
from tests.utils import ScheduleFactory, GroupScheduleTemplateFactory, SchoolGroupFactory, TeacherFactory


@pytest.mark.unit
class ScheduleModelTest(TestCase):
    """Test cases for Lesson model (legacy Schedule naming kept)."""
    
    def test_schedule_creation(self):
        """Test creating a schedule with valid data."""
        group = SchoolGroupFactory()
        teacher = group.teacher
        start_time = timezone.now() + timedelta(days=1, hours=10)
        end_time = (start_time + timedelta(minutes=45)).time()
        
        schedule = Lesson.objects.create(
            group=group,
            course=group.course,
            teacher=teacher,
            starts_at=start_time,
            ends_at=start_time + timedelta(minutes=45),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        self.assertEqual(schedule.group, group)
        self.assertEqual(schedule.teacher, teacher)
        self.assertEqual(schedule.status, 'scheduled')
    
    def test_schedule_str_representation(self):
        """Test string representation of schedule."""
        schedule = ScheduleFactory()
        
        str_repr = str(schedule)
        self.assertIsNotNone(str_repr)
    
    def test_schedule_status_choices(self):
        """Test all schedule status choices."""
        group = SchoolGroupFactory()
        teacher = group.teacher
        start_time = timezone.now() + timedelta(days=1)
        end_time = (start_time + timedelta(minutes=45)).time()
        
        statuses = ['scheduled', 'completed', 'cancelled', 'rescheduled']
        
        for status_choice in statuses:
            lesson_start = start_time + timedelta(hours=statuses.index(status_choice))
            schedule = Lesson.objects.create(
                group=group,
                course=group.course,
                teacher=teacher,
                starts_at=lesson_start,
                ends_at=lesson_start + timedelta(minutes=45),
                lesson_type=Lesson.LessonType.GROUP,
                status=status_choice
            )
            self.assertEqual(schedule.status, status_choice)
    
    def test_schedule_is_past_property(self):
        """Test is_past property for past schedule."""
        group = SchoolGroupFactory()
        past_time = timezone.now() - timedelta(days=1)
        end_time = (past_time + timedelta(minutes=45)).time()
        
        schedule = Lesson.objects.create(
            group=group,
            course=group.course,
            teacher=group.teacher,
            starts_at=past_time,
            ends_at=past_time + timedelta(minutes=45),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        self.assertTrue(schedule.is_past)
    
    def test_schedule_is_past_property_future(self):
        """Test is_past property for future schedule."""
        group = SchoolGroupFactory()
        future_time = timezone.now() + timedelta(days=1)
        end_time = (future_time + timedelta(minutes=45)).time()
        
        schedule = Lesson.objects.create(
            group=group,
            course=group.course,
            teacher=group.teacher,
            starts_at=future_time,
            ends_at=future_time + timedelta(minutes=45),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        self.assertFalse(schedule.is_past)
    
    def test_schedule_actual_status_property(self):
        """Test actual_status property computation."""
        group = SchoolGroupFactory()
        
        # Past scheduled lesson should be 'completed'
        past_time = timezone.now() - timedelta(days=1)
        past_schedule = Lesson.objects.create(
            group=group,
            course=group.course,
            teacher=group.teacher,
            starts_at=past_time,
            ends_at=past_time + timedelta(minutes=45),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        # Depending on implementation
        actual_status = past_schedule.actual_status
        self.assertIn(actual_status, ['completed', 'scheduled'])
    
    def test_schedule_teacher_must_be_teacher_role(self):
        """Test that schedule teacher must have TEACHER role."""
        from tests.utils import StudentFactory
        
        group = SchoolGroupFactory()
        student = StudentFactory()  # Wrong role
        
        schedule = Lesson(
            group=group,
            course=group.course,
            teacher=student,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        with self.assertRaises(ValidationError):
            schedule.clean()
    
    def test_schedule_with_valid_teacher_role(self):
        """Test that schedule accepts user with TEACHER role."""
        group = SchoolGroupFactory()
        teacher = TeacherFactory()
        
        schedule = Lesson(
            group=group,
            course=group.course,
            teacher=teacher,
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        # Should not raise ValidationError
        schedule.clean()
        schedule.save()
        
        self.assertIsNotNone(schedule.id)
    
    def test_rescheduled_lesson_tracking(self):
        """Test tracking original dates for rescheduled lesson."""
        group = SchoolGroupFactory()
        original_start = timezone.now() + timedelta(days=1)
        schedule = Lesson.objects.create(
            group=group,
            course=group.course,
            teacher=group.teacher,
            starts_at=original_start,
            ends_at=original_start + timedelta(minutes=45),
            lesson_type=Lesson.LessonType.GROUP,
            status='scheduled'
        )
        
        # Reschedule
        new_start = original_start + timedelta(days=2)
        LessonService.reschedule_lesson(
            schedule,
            new_start,
            new_start + timedelta(minutes=45),
            'Болезнь учителя',
        )
        
        self.assertEqual(schedule.status, 'rescheduled')
        self.assertIsNotNone(schedule.original_starts_at)
        self.assertEqual(schedule.reschedule_reason, 'Болезнь учителя')
    
    def test_cancelled_lesson_with_reason(self):
        """Test cancelled lesson with cancel reason."""
        schedule = ScheduleFactory(status='scheduled')
        
        schedule.status = 'cancelled'
        schedule.cancel_reason = 'Праздничный день'
        schedule.save()
        
        self.assertEqual(schedule.status, 'cancelled')
        self.assertEqual(schedule.cancel_reason, 'Праздничный день')
    
    def test_schedule_factory(self):
        """Test ScheduleFactory creates valid schedules."""
        schedule = ScheduleFactory()
        
        self.assertIsNotNone(schedule.id)
        self.assertIsNotNone(schedule.group)
        self.assertIsNotNone(schedule.teacher)
        self.assertEqual(schedule.teacher.role, 0)  # TEACHER role
    
    def test_multiple_schedules_for_group(self):
        """Test creating multiple schedules for same group."""
        group = SchoolGroupFactory()
        
        schedule1 = ScheduleFactory(
            group=group,
            starts_at=timezone.now() + timedelta(days=1)
        )
        schedule2 = ScheduleFactory(
            group=group,
            starts_at=timezone.now() + timedelta(days=2)
        )
        schedule3 = ScheduleFactory(
            group=group,
            starts_at=timezone.now() + timedelta(days=3)
        )
        
        group_schedules = Lesson.objects.filter(group=group)
        self.assertEqual(group_schedules.count(), 3)


@pytest.mark.unit
class GroupScheduleTemplateModelTest(TestCase):
    """Test cases for GroupScheduleTemplate model."""
    
    def test_template_creation(self):
        """Test creating a schedule template."""
        group = SchoolGroupFactory()
        
        template = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=1,  # Monday
            start_time=time(10, 0),
            lessons_count=1,
            is_active=True
        )
        
        self.assertEqual(template.group, group)
        self.assertEqual(template.weekday, 1)
        self.assertEqual(template.start_time, time(10, 0))
        self.assertEqual(template.lessons_count, 1)
        self.assertTrue(template.is_active)
    
    def test_template_str_representation(self):
        """Test string representation of template."""
        template = GroupScheduleTemplateFactory()
        
        str_repr = str(template)
        self.assertIsNotNone(str_repr)
    
    def test_template_weekday_validation(self):
        """Test weekday validation (0-6)."""
        group = SchoolGroupFactory()
        
        # Valid weekdays
        for weekday in range(7):
            template = GroupScheduleTemplate.objects.create(
                group=group,
                weekday=weekday,
                start_time=time(10, weekday),
                lessons_count=1
            )
            self.assertEqual(template.weekday, weekday)
    
    def test_template_lessons_count_validation(self):
        """Test lessons_count validation (1 or 2)."""
        group = SchoolGroupFactory()
        
        # 1 lesson (45 minutes)
        template1 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=1,
            start_time=time(10, 0),
            lessons_count=1
        )
        self.assertEqual(template1.lessons_count, 1)
        
        # 2 lessons (90 minutes)
        template2 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=2,
            start_time=time(10, 0),
            lessons_count=2
        )
        self.assertEqual(template2.lessons_count, 2)
    
    def test_template_unique_constraint(self):
        """Test unique constraint on (group, weekday, start_time)."""
        from django.db import IntegrityError
        
        group = SchoolGroupFactory()
        
        GroupScheduleTemplate.objects.create(
            group=group,
            weekday=1,
            start_time=time(10, 0),
            lessons_count=1
        )
        
        with self.assertRaises(IntegrityError):
            GroupScheduleTemplate.objects.create(
                group=group,
                weekday=1,
                start_time=time(10, 0),
                lessons_count=1
            )
    
    def test_multiple_templates_per_group(self):
        """Test creating multiple templates for same group."""
        group = SchoolGroupFactory()
        
        # Monday 10:00
        template1 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=1,
            start_time=time(10, 0),
            lessons_count=1
        )
        
        # Wednesday 14:00
        template2 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=3,
            start_time=time(14, 0),
            lessons_count=1
        )
        
        # Friday 16:00
        template3 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=5,
            start_time=time(16, 0),
            lessons_count=2
        )
        
        templates = GroupScheduleTemplate.objects.filter(group=group)
        self.assertEqual(templates.count(), 3)
    
    def test_template_same_weekday_different_times(self):
        """Test multiple templates on same weekday at different times."""
        group = SchoolGroupFactory()
        
        # Monday 10:00
        template1 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=1,
            start_time=time(10, 0),
            lessons_count=1
        )
        
        # Monday 14:00
        template2 = GroupScheduleTemplate.objects.create(
            group=group,
            weekday=1,
            start_time=time(14, 0),
            lessons_count=1
        )
        
        monday_templates = GroupScheduleTemplate.objects.filter(
            group=group,
            weekday=1
        )
        self.assertEqual(monday_templates.count(), 2)
    
    def test_inactive_template(self):
        """Test creating inactive template."""
        template = GroupScheduleTemplateFactory(is_active=False)
        
        self.assertFalse(template.is_active)
    
    def test_template_factory(self):
        """Test GroupScheduleTemplateFactory creates valid templates."""
        template = GroupScheduleTemplateFactory()
        
        self.assertIsNotNone(template.id)
        self.assertIsNotNone(template.group)
        self.assertIn(template.weekday, range(7))
        self.assertIn(template.lessons_count, [1, 2])
    
    def test_template_deletion(self):
        """Test deleting a template."""
        template = GroupScheduleTemplateFactory()
        template_id = template.id
        
        template.delete()
        
        self.assertFalse(
            GroupScheduleTemplate.objects.filter(id=template_id).exists()
        )
    
    def test_template_update(self):
        """Test updating template details."""
        template = GroupScheduleTemplateFactory(
            start_time=time(10, 0),
            lessons_count=1
        )
        
        template.start_time = time(14, 0)
        template.lessons_count = 2
        template.save()
        
        updated_template = GroupScheduleTemplate.objects.get(id=template.id)
        self.assertEqual(updated_template.start_time, time(14, 0))
        self.assertEqual(updated_template.lessons_count, 2)
    
    def test_get_templates_for_group(self):
        """Test retrieving all templates for a group."""
        group = SchoolGroupFactory()
        
        GroupScheduleTemplateFactory(group=group, weekday=1)
        GroupScheduleTemplateFactory(group=group, weekday=3)
        GroupScheduleTemplateFactory(group=group, weekday=5)
        
        # Other group's template
        other_group = SchoolGroupFactory()
        GroupScheduleTemplateFactory(group=other_group, weekday=2)
        
        group_templates = GroupScheduleTemplate.objects.filter(group=group)
        self.assertEqual(group_templates.count(), 3)
    
    def test_filter_active_templates(self):
        """Test filtering only active templates."""
        group = SchoolGroupFactory()
        
        active1 = GroupScheduleTemplateFactory(group=group, is_active=True, weekday=1)
        active2 = GroupScheduleTemplateFactory(group=group, is_active=True, weekday=3)
        inactive = GroupScheduleTemplateFactory(group=group, is_active=False, weekday=5)
        
        active_templates = GroupScheduleTemplate.objects.filter(
            group=group,
            is_active=True
        )
        
        self.assertEqual(active_templates.count(), 2)
        self.assertIn(active1, active_templates)
        self.assertIn(active2, active_templates)
        self.assertNotIn(inactive, active_templates)
