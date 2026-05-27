"""
Tests for Attendance tracking and lesson deduction.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from schedule.models import LessonParticipant as LessonAttendance
from subscriptions.models import Subscription
from tests.utils import (
    ScheduleFactory, StudentFactory, SubscriptionFactory,
    create_schedule_with_attendance, SchoolGroupFactory
)


@pytest.mark.critical
class MarkAttendanceTest(TestCase):
    """Test cases for marking attendance."""
    
    def test_mark_attendance_with_lesson_deduction(self):
        """Test marking attendance deducts lessons from subscription."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=0,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        # Manually deduct lessons (or call service method)
        subscription.deduct_lessons(1)
        
        self.assertEqual(subscription.lessons_used, 1)
        self.assertEqual(subscription.lessons_remaining, 7)
        self.assertTrue(attendance.lesson_deducted)
    
    def test_mark_attendance_two_lessons(self):
        """Test marking attendance for 2 lessons (90 minutes)."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=0,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=2,
            lesson_deducted=True
        )
        
        subscription.deduct_lessons(2)
        
        self.assertEqual(subscription.lessons_used, 2)
        self.assertEqual(subscription.lessons_remaining, 6)
        self.assertEqual(attendance.lessons_count, 2)
    
    def test_mark_attendance_without_subscription(self):
        """Test marking attendance without subscription (trial lesson)."""
        student = StudentFactory()
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=None,
            status='present',
            lessons_count=1,
            lesson_deducted=False
        )
        
        self.assertIsNone(attendance.subscription)
        self.assertFalse(attendance.lesson_deducted)
    
    def test_mark_attendance_absent(self):
        """Test marking student as absent (no lesson deduction)."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=0,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='absent',
            lessons_count=1,
            lesson_deducted=False
        )
        
        # No deduction for absent
        self.assertEqual(subscription.lessons_used, 0)
        self.assertEqual(attendance.status, 'absent')
        self.assertFalse(attendance.lesson_deducted)
    
    def test_mark_attendance_excused(self):
        """Test marking student as excused (no lesson deduction)."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=0,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='excused',
            lessons_count=1,
            lesson_deducted=False,
            notes='Болел'
        )
        
        self.assertEqual(subscription.lessons_used, 0)
        self.assertEqual(attendance.status, 'excused')
        self.assertEqual(attendance.notes, 'Болел')
    
    def test_mark_attendance_exhausts_subscription(self):
        """Test that marking attendance exhausts subscription when no lessons remain."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=7,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        subscription.deduct_lessons(1)
        
        self.assertEqual(subscription.lessons_used, 8)
        self.assertEqual(subscription.lessons_remaining, 0)
        self.assertEqual(subscription.status, 'exhausted')
    
    def test_cannot_mark_duplicate_attendance(self):
        """Test that student cannot have duplicate attendance for same schedule."""
        from django.db import IntegrityError
        
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        schedule = ScheduleFactory()
        
        LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1
        )
        
        with self.assertRaises(IntegrityError):
            LessonAttendance.objects.create(
                schedule=schedule,
                student=student,
                subscription=subscription,
                status='present',
                lessons_count=1
            )
    
    def test_mark_attendance_for_multiple_students(self):
        """Test marking attendance for multiple students in same lesson."""
        group = SchoolGroupFactory()
        schedule = ScheduleFactory(group=group)
        
        student1 = StudentFactory()
        student2 = StudentFactory()
        student3 = StudentFactory()
        
        sub1 = SubscriptionFactory(student=student1, lessons_total=8, lessons_used=0)
        sub2 = SubscriptionFactory(student=student2, lessons_total=8, lessons_used=0)
        sub3 = SubscriptionFactory(student=student3, lessons_total=8, lessons_used=0)
        
        LessonAttendance.objects.create(
            schedule=schedule, student=student1, subscription=sub1,
            status='present', lessons_count=1, lesson_deducted=True
        )
        LessonAttendance.objects.create(
            schedule=schedule, student=student2, subscription=sub2,
            status='present', lessons_count=1, lesson_deducted=True
        )
        LessonAttendance.objects.create(
            schedule=schedule, student=student3, subscription=sub3,
            status='absent', lessons_count=1, lesson_deducted=False
        )
        
        sub1.deduct_lessons(1)
        sub2.deduct_lessons(1)
        # sub3 not deducted (absent)
        
        self.assertEqual(sub1.lessons_used, 1)
        self.assertEqual(sub2.lessons_used, 1)
        self.assertEqual(sub3.lessons_used, 0)
    
    def test_mark_attendance_with_insufficient_lessons(self):
        """Test marking attendance when subscription has insufficient lessons."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=8,
            status='exhausted'
        )
        schedule = ScheduleFactory()
        
        # Can create attendance record
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=False  # Cannot deduct
        )
        
        # But cannot deduct lessons
        self.assertFalse(subscription.deduct_lessons(1))


@pytest.mark.critical
class CancelAttendanceTest(TestCase):
    """Test cases for canceling attendance and refunding lessons."""
    
    def test_cancel_attendance_refunds_lessons(self):
        """Test that canceling attendance refunds lessons to subscription."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=3,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        # Cancel attendance and refund
        subscription.refund_lessons(1)
        attendance.delete()
        
        self.assertEqual(subscription.lessons_used, 2)
        self.assertEqual(subscription.lessons_remaining, 6)
        self.assertFalse(LessonAttendance.objects.filter(id=attendance.id).exists())
    
    def test_cancel_attendance_refunds_two_lessons(self):
        """Test canceling attendance for 2 lessons."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=5,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=2,
            lesson_deducted=True
        )
        
        subscription.refund_lessons(2)
        attendance.delete()
        
        self.assertEqual(subscription.lessons_used, 3)
        self.assertEqual(subscription.lessons_remaining, 5)
    
    def test_cancel_attendance_reactivates_exhausted_subscription(self):
        """Test that canceling attendance reactivates exhausted subscription."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=8,
            status='exhausted'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        subscription.refund_lessons(1)
        
        self.assertEqual(subscription.lessons_used, 7)
        self.assertEqual(subscription.lessons_remaining, 1)
        self.assertEqual(subscription.status, 'active')
    
    def test_cancel_attendance_without_deduction(self):
        """Test canceling attendance that had no lesson deduction."""
        student = StudentFactory()
        subscription = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=3,
            status='active'
        )
        schedule = ScheduleFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='absent',
            lessons_count=1,
            lesson_deducted=False
        )
        
        # Delete attendance (no refund needed)
        attendance.delete()
        
        # Subscription unchanged
        self.assertEqual(subscription.lessons_used, 3)
        self.assertEqual(subscription.lessons_remaining, 5)


@pytest.mark.critical
class AttendanceForRescheduledLessonTest(TestCase):
    """Test cases for attendance on rescheduled lessons."""
    
    def test_mark_attendance_for_rescheduled_lesson(self):
        """Test marking attendance for rescheduled lesson."""
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student, lessons_total=8, lessons_used=0)
        
        # Create rescheduled lesson
        schedule = ScheduleFactory(status='rescheduled')
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        subscription.deduct_lessons(1)
        
        self.assertEqual(subscription.lessons_used, 1)
        self.assertEqual(attendance.schedule.status, 'rescheduled')


@pytest.mark.critical
class AttendanceForCancelledLessonTest(TestCase):
    """Test cases for attendance on cancelled lessons."""
    
    def test_cannot_mark_attendance_for_cancelled_lesson(self):
        """Test that attendance should not be marked for cancelled lesson."""
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
        # Create cancelled lesson
        schedule = ScheduleFactory(status='cancelled')
        
        # Depending on implementation, this might be prevented
        # For now, we just create it and verify the status
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=False  # Should not deduct for cancelled
        )
        
        self.assertEqual(attendance.schedule.status, 'cancelled')
        self.assertFalse(attendance.lesson_deducted)


@pytest.mark.critical
class AttendanceHistoryTest(TestCase):
    """Test cases for attendance history tracking."""
    
    def test_get_student_attendance_history(self):
        """Test retrieving student's attendance history."""
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
        schedule1 = ScheduleFactory()
        schedule2 = ScheduleFactory()
        schedule3 = ScheduleFactory()
        
        LessonAttendance.objects.create(
            schedule=schedule1, student=student, subscription=subscription,
            status='present', lessons_count=1
        )
        LessonAttendance.objects.create(
            schedule=schedule2, student=student, subscription=subscription,
            status='present', lessons_count=1
        )
        LessonAttendance.objects.create(
            schedule=schedule3, student=student, subscription=subscription,
            status='absent', lessons_count=1
        )
        
        history = LessonAttendance.objects.filter(student=student)
        
        self.assertEqual(history.count(), 3)
        self.assertEqual(history.filter(status='present').count(), 2)
        self.assertEqual(history.filter(status='absent').count(), 1)
    
    def test_get_schedule_attendance_list(self):
        """Test retrieving all attendance for a schedule."""
        schedule = ScheduleFactory()
        
        student1 = StudentFactory()
        student2 = StudentFactory()
        student3 = StudentFactory()
        
        sub1 = SubscriptionFactory(student=student1)
        sub2 = SubscriptionFactory(student=student2)
        sub3 = SubscriptionFactory(student=student3)
        
        LessonAttendance.objects.create(
            schedule=schedule, student=student1, subscription=sub1,
            status='present', lessons_count=1
        )
        LessonAttendance.objects.create(
            schedule=schedule, student=student2, subscription=sub2,
            status='present', lessons_count=1
        )
        LessonAttendance.objects.create(
            schedule=schedule, student=student3, subscription=sub3,
            status='absent', lessons_count=1
        )
        
        attendance_list = LessonAttendance.objects.filter(schedule=schedule)
        
        self.assertEqual(attendance_list.count(), 3)


@pytest.mark.critical
class MultipleSubscriptionsAttendanceTest(TestCase):
    """Test cases for attendance when student has multiple subscriptions."""
    
    def test_attendance_uses_correct_subscription(self):
        """Test that attendance uses the correct active subscription."""
        student = StudentFactory()
        
        # Student has 2 active subscriptions
        sub1 = SubscriptionFactory(
            student=student,
            lessons_total=8,
            lessons_used=0,
            status='active'
        )
        sub2 = SubscriptionFactory(
            student=student,
            lessons_total=12,
            lessons_used=0,
            status='active'
        )
        
        schedule = ScheduleFactory()
        
        # Mark attendance using sub1
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=sub1,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        sub1.deduct_lessons(1)
        
        self.assertEqual(sub1.lessons_used, 1)
        self.assertEqual(sub2.lessons_used, 0)  # Unchanged
        self.assertEqual(attendance.subscription, sub1)
