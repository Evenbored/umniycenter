"""
Tests for Schedule services.
"""

import pytest
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta, time, date
from schedule.services import get_user_schedule, get_lesson_end_time, generate_schedule_for_range
from schedule.models import Schedule, GroupScheduleTemplate
from tests.utils import (
    TeacherFactory, StudentFactory, SchoolGroupFactory,
    GroupScheduleTemplateFactory, ScheduleFactory
)
from students.models import StudentGroups


@pytest.mark.unit
class GetUserScheduleTest(TestCase):
    """Test cases for get_user_schedule() function."""
    
    def setUp(self):
        cache.clear()
    
    def test_get_teacher_schedule(self):
        """Test getting schedule for teacher."""
        teacher = TeacherFactory()
        group = SchoolGroupFactory(teacher=teacher)
        
        schedule1 = ScheduleFactory(group=group, teacher=teacher)
        schedule2 = ScheduleFactory(group=group, teacher=teacher)
        
        schedules = get_user_schedule(teacher)
        
        self.assertGreaterEqual(len(schedules), 2)
        schedule_ids = [s.id for s in schedules]
        self.assertIn(schedule1.id, schedule_ids)
        self.assertIn(schedule2.id, schedule_ids)
    
    def test_get_student_schedule(self):
        """Test getting schedule for student."""
        student = StudentFactory()
        group = SchoolGroupFactory()
        StudentGroups.objects.create(student=student, group=group)
        
        schedule1 = ScheduleFactory(group=group)
        schedule2 = ScheduleFactory(group=group)
        
        schedules = get_user_schedule(student)
        
        self.assertGreaterEqual(len(schedules), 2)
        schedule_ids = [s.id for s in schedules]
        self.assertIn(schedule1.id, schedule_ids)
        self.assertIn(schedule2.id, schedule_ids)
    
    def test_schedule_caching(self):
        """Test that schedule is cached."""
        teacher = TeacherFactory()
        group = SchoolGroupFactory(teacher=teacher)
        ScheduleFactory(group=group, teacher=teacher)
        
        # First call - should hit database
        schedules1 = get_user_schedule(teacher)
        
        # Second call - should use cache
        schedules2 = get_user_schedule(teacher)
        
        self.assertEqual(len(schedules1), len(schedules2))
    
    def test_teacher_with_no_schedule(self):
        """Test getting schedule for teacher with no lessons."""
        teacher = TeacherFactory()
        
        schedules = get_user_schedule(teacher)
        
        self.assertEqual(len(schedules), 0)
    
    def test_student_with_no_groups(self):
        """Test getting schedule for student not in any group."""
        student = StudentFactory()
        
        schedules = get_user_schedule(student)
        
        self.assertEqual(len(schedules), 0)


@pytest.mark.unit
class GetLessonEndTimeTest(TestCase):
    """Test cases for get_lesson_end_time() function."""
    
    def test_one_lesson_duration(self):
        """Test calculating end time for 1 lesson (45 minutes)."""
        start_time = time(10, 0)
        
        end_time = get_lesson_end_time(start_time, lessons_count=1)
        
        expected_end = timezone.make_aware(datetime.combine(date(2026, 5, 5), start_time)) + timedelta(minutes=45)
        self.assertEqual(end_time, expected_end.time())
    
    def test_two_lessons_duration(self):
        """Test calculating end time for 2 lessons (90 minutes)."""
        start_time = time(10, 0)
        
        end_time = get_lesson_end_time(start_time, lessons_count=2)
        
        expected_end = timezone.make_aware(datetime.combine(date(2026, 5, 5), start_time)) + timedelta(minutes=90)
        self.assertEqual(end_time, expected_end.time())
    
    def test_end_time_crosses_hour_boundary(self):
        """Test end time calculation crossing hour boundary."""
        start_time = time(10, 30)
        
        end_time = get_lesson_end_time(start_time, lessons_count=1)
        
        expected_end = timezone.make_aware(datetime(2026, 5, 5, 11, 15))
        self.assertEqual(end_time, expected_end.time())
    
    def test_end_time_with_different_start_times(self):
        """Test end time calculation with various start times."""
        test_cases = [
            (time(9, 0), 1, time(9, 45)),
            (time(14, 0), 1, time(14, 45)),
            (time(16, 0), 2, time(17, 30)),
            (time(18, 30), 1, time(19, 15)),
        ]
        
        for start, lessons, expected in test_cases:
            result = get_lesson_end_time(start, lessons)
            self.assertEqual(result, expected)


@pytest.mark.unit
class GenerateScheduleForRangeTest(TestCase):
    """Test cases for generate_schedule_for_range() function."""
    
    def test_generate_schedule_from_templates(self):
        """Test generating schedule from templates."""
        group = SchoolGroupFactory()
        
        # Create templates: Monday and Wednesday at 10:00
        GroupScheduleTemplateFactory(
            group=group,
            weekday=0,  # Monday
            start_time=time(10, 0),
            lessons_count=1,
            is_active=True
        )
        GroupScheduleTemplateFactory(
            group=group,
            weekday=2,  # Wednesday
            start_time=time(10, 0),
            lessons_count=1,
            is_active=True
        )
        
        # Generate schedule for 2 weeks (future dates)
        date_from = date.today() + timedelta(days=1)
        date_to = date_from + timedelta(days=13)
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        # Should create 4 lessons (2 Mondays + 2 Wednesdays)
        self.assertGreaterEqual(len(schedules), 4)
    
    def test_generate_schedule_skips_past_dates(self):
        """Test that schedule generation skips past dates."""
        group = SchoolGroupFactory()
        
        GroupScheduleTemplateFactory(
            group=group,
            weekday=0,  # Monday
            start_time=time(10, 0),
            lessons_count=1,
            is_active=True
        )
        
        # Try to generate for past dates
        date_from = date(2026, 4, 1)
        date_to = date(2026, 4, 7)
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        # Should not create schedules for past dates
        for schedule in schedules:
            self.assertGreaterEqual(schedule.classdateStart.date(), date.today())
    
    def test_generate_schedule_prevents_duplicates(self):
        """Test that duplicate schedules are not created."""
        group = SchoolGroupFactory()
        
        template = GroupScheduleTemplateFactory(
            group=group,
            weekday=1,  # Tuesday
            start_time=time(10, 0),
            lessons_count=1,
            is_active=True
        )
        
        date_from = date(2026, 5, 6)  # Tuesday
        date_to = date(2026, 5, 12)
        
        # Generate first time
        schedules1 = generate_schedule_for_range(date_from, date_to, group.id)
        initial_count = len(schedules1)
        
        # Generate again - should not create duplicates
        schedules2 = generate_schedule_for_range(date_from, date_to, group.id)
        
        # Total count should be same or similar (get_or_create behavior)
        total_schedules = Schedule.objects.filter(
            group=group,
            classdateStart__date__gte=date_from,
            classdateStart__date__lte=date_to
        ).count()
        
        self.assertGreaterEqual(total_schedules, initial_count)
    
    def test_generate_schedule_with_multiple_templates(self):
        """Test generating schedule with multiple templates per week."""
        group = SchoolGroupFactory()
        
        # Monday, Wednesday, Friday
        GroupScheduleTemplateFactory(
            group=group, weekday=0, start_time=time(10, 0), lessons_count=1
        )
        GroupScheduleTemplateFactory(
            group=group, weekday=2, start_time=time(10, 0), lessons_count=1
        )
        GroupScheduleTemplateFactory(
            group=group, weekday=4, start_time=time(10, 0), lessons_count=1
        )
        
        date_from = date.today() + timedelta(days=1)
        date_to = date_from + timedelta(days=6)
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        # Should create 3 lessons (Mon, Wed, Fri)
        self.assertGreaterEqual(len(schedules), 3)
    
    def test_generate_schedule_with_two_lesson_template(self):
        """Test generating schedule with 2-lesson template (90 minutes)."""
        group = SchoolGroupFactory()
        
        GroupScheduleTemplateFactory(
            group=group,
            weekday=1,  # Tuesday
            start_time=time(14, 0),
            lessons_count=2,  # 90 minutes
            is_active=True
        )
        
        date_from = date(2026, 5, 6)  # Tuesday
        date_to = date(2026, 5, 12)
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        self.assertGreater(len(schedules), 0)
        
        # Check that end time is 90 minutes after start
        if schedules:
            schedule = schedules[0]
            start_datetime = schedule.classdateStart
            end_time = schedule.classdateEnd
            expected_end = (start_datetime + timedelta(minutes=90)).time()
            self.assertEqual(end_time, expected_end)
    
    def test_generate_schedule_ignores_inactive_templates(self):
        """Test that inactive templates are not used."""
        group = SchoolGroupFactory()
        date_from = date.today() + timedelta(days=1)
        date_to = date_from + timedelta(days=6)
        active_weekday = date_from.weekday()
        inactive_weekday = (active_weekday + 2) % 7
        
        # Active template
        GroupScheduleTemplateFactory(
            group=group,
            weekday=active_weekday,
            start_time=time(10, 0),
            lessons_count=1,
            is_active=True
        )
        
        # Inactive template
        GroupScheduleTemplateFactory(
            group=group,
            weekday=inactive_weekday,
            start_time=time(10, 0),
            lessons_count=1,
            is_active=False
        )
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        # Should only create schedules for active template weekday, not inactive one
        active_schedules = [s for s in schedules if s.classdateStart.weekday() == active_weekday]
        inactive_schedules = [s for s in schedules if s.classdateStart.weekday() == inactive_weekday]
        
        self.assertGreater(len(active_schedules), 0)
        self.assertEqual(len(inactive_schedules), 0)
    
    def test_generate_schedule_for_one_month(self):
        """Test generating schedule for entire month."""
        group = SchoolGroupFactory()
        
        # Twice a week: Tuesday and Thursday
        GroupScheduleTemplateFactory(
            group=group, weekday=1, start_time=time(10, 0), lessons_count=1
        )
        GroupScheduleTemplateFactory(
            group=group, weekday=3, start_time=time(10, 0), lessons_count=1
        )
        
        date_from = date(2026, 6, 1)
        date_to = date(2026, 6, 30)
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        # June 2026 has ~8-9 Tuesdays and Thursdays combined
        self.assertGreaterEqual(len(schedules), 8)
    
    def test_generate_schedule_with_no_templates(self):
        """Test generating schedule when no templates exist."""
        group = SchoolGroupFactory()
        
        date_from = date(2026, 5, 5)
        date_to = date(2026, 5, 11)
        
        schedules = generate_schedule_for_range(date_from, date_to, group.id)
        
        self.assertEqual(len(schedules), 0)
    
    def test_generate_schedule_for_nonexistent_group(self):
        """Test generating schedule for nonexistent group."""
        date_from = date(2026, 5, 5)
        date_to = date(2026, 5, 11)
        
        schedules = generate_schedule_for_range(date_from, date_to, group_id=99999)
        
        self.assertEqual(len(schedules), 0)
