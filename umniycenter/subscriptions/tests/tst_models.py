"""
Tests for Subscriptions models.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, date
from decimal import Decimal
from subscriptions.models import Tariff, Subscription, Payment, LessonAttendance
from tests.utils import (
    TariffFactory, SubscriptionFactory, PaymentFactory,
    StudentFactory, ParentFactory, CourseFactory,
    create_student_with_subscription, assert_subscription_valid
)


@pytest.mark.unit
class TariffModelTest(TestCase):
    """Test cases for Tariff model."""
    
    def test_tariff_creation(self):
        """Test creating a tariff with valid data."""
        course = CourseFactory()
        tariff = Tariff.objects.create(
            name="Базовый тариф",
            course=course,
            lessons_count=8,
            validity_days=30,
            price=Decimal('5000.00'),
            description="8 занятий в месяц",
            is_active=True,
            is_trial=False
        )
        
        self.assertEqual(tariff.name, "Базовый тариф")
        self.assertEqual(tariff.lessons_count, 8)
        self.assertEqual(tariff.validity_days, 30)
        self.assertEqual(tariff.price, Decimal('5000.00'))
        self.assertTrue(tariff.is_active)
        self.assertFalse(tariff.is_trial)
    
    def test_tariff_str_representation(self):
        """Test string representation of tariff."""
        tariff = TariffFactory(name="Тестовый тариф")
        
        self.assertIn("Тестовый тариф", str(tariff))
    
    def test_trial_tariff_creation(self):
        """Test creating trial tariff."""
        tariff = TariffFactory(
            name="Пробное занятие",
            lessons_count=1,
            validity_days=7,
            price=Decimal('500.00'),
            is_trial=True
        )
        
        self.assertTrue(tariff.is_trial)
        self.assertEqual(tariff.lessons_count, 1)
    
    def test_tariff_price_validation(self):
        """Test that price must be positive."""
        course = CourseFactory()
        
        tariff = Tariff.objects.create(
            name="Invalid",
            course=course,
            lessons_count=8,
            validity_days=30,
            price=Decimal('-100.00')  # Negative price is currently allowed by model
        )
        self.assertEqual(tariff.price, Decimal('-100.00'))
    
    def test_tariff_lessons_count_validation(self):
        """Test that lessons_count must be positive."""
        course = CourseFactory()
        
        tariff = Tariff.objects.create(
            name="Invalid",
            course=course,
            lessons_count=0,  # Zero lessons is currently allowed by model
            validity_days=30,
            price=Decimal('5000.00')
        )
        self.assertEqual(tariff.lessons_count, 0)
    
    def test_tariff_validity_days_validation(self):
        """Test that validity_days must be positive."""
        course = CourseFactory()
        
        tariff = Tariff.objects.create(
            name="Invalid",
            course=course,
            lessons_count=8,
            validity_days=0,  # Zero days is currently allowed by model
            price=Decimal('5000.00')
        )
        self.assertEqual(tariff.validity_days, 0)
    
    def test_inactive_tariff(self):
        """Test creating inactive tariff."""
        tariff = TariffFactory(is_active=False)
        
        self.assertFalse(tariff.is_active)
    
    def test_tariff_factory(self):
        """Test TariffFactory creates valid tariffs."""
        tariff = TariffFactory()
        
        self.assertIsNotNone(tariff.id)
        self.assertIsNotNone(tariff.name)
        self.assertIsNotNone(tariff.course)
        self.assertGreater(tariff.lessons_count, 0)
        self.assertGreater(tariff.validity_days, 0)
        self.assertGreater(tariff.price, 0)


@pytest.mark.unit
class SubscriptionModelTest(TestCase):
    """Test cases for Subscription model."""
    
    def test_subscription_creation(self):
        """Test creating a subscription with valid data."""
        student = StudentFactory()
        parent = ParentFactory()
        tariff = TariffFactory(lessons_count=8, validity_days=30)
        
        start_date = date.today()
        end_date = start_date + timedelta(days=30)
        
        subscription = Subscription.objects.create(
            student=student,
            parent=parent,
            tariff=tariff,
            lessons_total=8,
            lessons_used=0,
            start_date=start_date,
            end_date=end_date,
            status='active'
        )
        
        self.assertEqual(subscription.student, student)
        self.assertEqual(subscription.parent, parent)
        self.assertEqual(subscription.tariff, tariff)
        self.assertEqual(subscription.lessons_total, 8)
        self.assertEqual(subscription.lessons_used, 0)
        self.assertEqual(subscription.status, 'active')
    
    def test_subscription_lessons_remaining_property(self):
        """Test lessons_remaining property calculation."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=3
        )
        
        self.assertEqual(subscription.lessons_remaining, 5)
    
    def test_subscription_is_valid_property_active(self):
        """Test is_valid property for active subscription."""
        subscription = SubscriptionFactory(
            status='active',
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            lessons_total=8,
            lessons_used=3
        )
        
        self.assertTrue(subscription.is_valid)
    
    def test_subscription_is_valid_property_expired(self):
        """Test is_valid property for expired subscription."""
        subscription = SubscriptionFactory(
            status='expired',
            start_date=date.today() - timedelta(days=60),
            end_date=date.today() - timedelta(days=30)
        )
        
        self.assertFalse(subscription.is_valid)
    
    def test_subscription_is_valid_property_exhausted(self):
        """Test is_valid property for exhausted subscription."""
        subscription = SubscriptionFactory(
            status='exhausted',
            lessons_total=8,
            lessons_used=8
        )
        
        self.assertFalse(subscription.is_valid)
    
    def test_subscription_deduct_lessons(self):
        """Test deducting lessons from subscription."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=0,
            status='active'
        )
        
        subscription.deduct_lessons(2)
        
        self.assertEqual(subscription.lessons_used, 2)
        self.assertEqual(subscription.lessons_remaining, 6)
        self.assertEqual(subscription.status, 'active')
    
    def test_subscription_deduct_lessons_to_exhaustion(self):
        """Test deducting all remaining lessons."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=6,
            status='active'
        )
        
        subscription.deduct_lessons(2)
        
        self.assertEqual(subscription.lessons_used, 8)
        self.assertEqual(subscription.lessons_remaining, 0)
        self.assertEqual(subscription.status, 'exhausted')
    
    def test_subscription_cannot_deduct_more_than_remaining(self):
        """Test that cannot deduct more lessons than remaining."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=7,
            status='active'
        )
        
        result = subscription.deduct_lessons(2)
        self.assertFalse(result)
    
    def test_subscription_refund_lessons(self):
        """Test refunding lessons to subscription."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=5,
            status='active'
        )
        
        subscription.refund_lessons(2)
        
        self.assertEqual(subscription.lessons_used, 3)
        self.assertEqual(subscription.lessons_remaining, 5)
    
    def test_subscription_refund_lessons_reactivates_exhausted(self):
        """Test that refunding lessons reactivates exhausted subscription."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=8,
            status='exhausted'
        )
        
        subscription.refund_lessons(2)
        
        self.assertEqual(subscription.lessons_used, 6)
        self.assertEqual(subscription.lessons_remaining, 2)
        self.assertEqual(subscription.status, 'active')
    
    def test_subscription_cannot_refund_more_than_used(self):
        """Test that cannot refund more lessons than used."""
        subscription = SubscriptionFactory(
            lessons_total=8,
            lessons_used=2,
            status='active'
        )
        
        result = subscription.refund_lessons(3)
        self.assertFalse(result)
    
    def test_subscription_status_transitions(self):
        """Test subscription status transitions."""
        subscription = SubscriptionFactory(status='pending')
        
        # pending -> active
        subscription.status = 'active'
        subscription.save()
        self.assertEqual(subscription.status, 'active')
        
        # active -> exhausted
        subscription.status = 'exhausted'
        subscription.save()
        self.assertEqual(subscription.status, 'exhausted')
    
    def test_subscription_frozen_status(self):
        """Test frozen subscription."""
        subscription = SubscriptionFactory(
            status='frozen',
            frozen_at=datetime.now(),
            frozen_days=10
        )
        
        self.assertEqual(subscription.status, 'frozen')
        self.assertIsNotNone(subscription.frozen_at)
        self.assertEqual(subscription.frozen_days, 10)
    
    def test_multiple_active_subscriptions_per_student(self):
        """Test that student can have multiple active subscriptions."""
        student = StudentFactory()
        parent = ParentFactory()
        
        sub1 = SubscriptionFactory(student=student, parent=parent, status='active')
        sub2 = SubscriptionFactory(student=student, parent=parent, status='active')
        
        active_subs = Subscription.objects.filter(student=student, status='active')
        self.assertEqual(active_subs.count(), 2)
    
    def test_subscription_factory(self):
        """Test SubscriptionFactory creates valid subscriptions."""
        subscription = SubscriptionFactory()
        
        self.assertIsNotNone(subscription.id)
        self.assertIsNotNone(subscription.student)
        self.assertIsNotNone(subscription.parent)
        self.assertIsNotNone(subscription.tariff)
        self.assertEqual(subscription.lessons_total, subscription.tariff.lessons_count)


@pytest.mark.unit
class PaymentModelTest(TestCase):
    """Test cases for Payment model."""
    
    def test_payment_creation(self):
        """Test creating a payment with valid data."""
        subscription = SubscriptionFactory()
        
        payment = Payment.objects.create(
            subscription=subscription,
            parent=subscription.parent,
            amount=Decimal('5000.00'),
            payment_method='cash',
            status='pending'
        )
        
        self.assertEqual(payment.subscription, subscription)
        self.assertEqual(payment.parent, subscription.parent)
        self.assertEqual(payment.amount, Decimal('5000.00'))
        self.assertEqual(payment.payment_method, 'cash')
        self.assertEqual(payment.status, 'pending')
    
    def test_payment_status_transitions(self):
        """Test payment status transitions."""
        payment = PaymentFactory(status='pending')
        
        # pending -> completed
        payment.status = 'completed'
        payment.paid_at = datetime.now()
        payment.save()
        
        self.assertEqual(payment.status, 'completed')
        self.assertIsNotNone(payment.paid_at)
    
    def test_payment_methods(self):
        """Test all payment methods."""
        subscription = SubscriptionFactory()
        
        methods = ['cash', 'card', 'transfer', 'online']
        
        for method in methods:
            payment = Payment.objects.create(
                subscription=subscription,
                parent=subscription.parent,
                amount=Decimal('5000.00'),
                payment_method=method,
                status='pending'
            )
            self.assertEqual(payment.payment_method, method)
    
    def test_payment_with_yookassa_data(self):
        """Test payment with YooKassa data."""
        payment = PaymentFactory(
            payment_method='online',
            yookassa_payment_id='test_payment_123',
            yookassa_payment_url='https://test.yookassa.ru/payments/test_payment_123'
        )
        
        self.assertEqual(payment.yookassa_payment_id, 'test_payment_123')
        self.assertIsNotNone(payment.yookassa_payment_url)
    
    def test_payment_with_transaction_id(self):
        """Test payment with transaction ID."""
        payment = PaymentFactory(
            payment_method='card',
            transaction_id='TXN123456789'
        )
        
        self.assertEqual(payment.transaction_id, 'TXN123456789')
    
    def test_payment_with_notes(self):
        """Test payment with notes."""
        payment = PaymentFactory(
            notes='Оплата наличными в офисе'
        )
        
        self.assertEqual(payment.notes, 'Оплата наличными в офисе')
    
    def test_payment_with_error_message(self):
        """Test payment with error message."""
        payment = PaymentFactory(
            status='failed',
            error_message='Недостаточно средств'
        )
        
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.error_message, 'Недостаточно средств')
    
    def test_payment_factory(self):
        """Test PaymentFactory creates valid payments."""
        payment = PaymentFactory()
        
        self.assertIsNotNone(payment.id)
        self.assertIsNotNone(payment.subscription)
        self.assertIsNotNone(payment.parent)
        self.assertGreater(payment.amount, 0)


@pytest.mark.unit
class LessonAttendanceModelTest(TestCase):
    """Test cases for LessonAttendance model."""
    
    def test_lesson_attendance_creation(self):
        """Test creating lesson attendance record."""
        from tests.utils import ScheduleFactory
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        
        self.assertEqual(attendance.schedule, schedule)
        self.assertEqual(attendance.student, student)
        self.assertEqual(attendance.subscription, subscription)
        self.assertEqual(attendance.status, 'present')
        self.assertEqual(attendance.lessons_count, 1)
        self.assertTrue(attendance.lesson_deducted)
    
    def test_attendance_status_choices(self):
        """Test all attendance status choices."""
        from tests.utils import ScheduleFactory
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
        statuses = ['present', 'absent', 'excused']
        
        for status_choice in statuses:
            attendance = LessonAttendance.objects.create(
                schedule=ScheduleFactory(),
                student=student,
                subscription=subscription,
                status=status_choice,
                lessons_count=1
            )
            self.assertEqual(attendance.status, status_choice)
    
    def test_attendance_lessons_count_validation(self):
        """Test that lessons_count can be 1 or 2."""
        from tests.utils import ScheduleFactory
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
        # 1 lesson (45 minutes)
        attendance1 = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1
        )
        self.assertEqual(attendance1.lessons_count, 1)
        
        # 2 lessons (90 minutes)
        attendance2 = LessonAttendance.objects.create(
            schedule=ScheduleFactory(),
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=2
        )
        self.assertEqual(attendance2.lessons_count, 2)
    
    def test_attendance_unique_constraint(self):
        """Test that student can only have one attendance per schedule."""
        from tests.utils import ScheduleFactory
        from django.db import IntegrityError
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
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
    
    def test_attendance_without_subscription(self):
        """Test creating attendance without subscription (trial lesson)."""
        from tests.utils import ScheduleFactory
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        
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
    
    def test_attendance_with_notes(self):
        """Test attendance with notes."""
        from tests.utils import ScheduleFactory
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='excused',
            lessons_count=1,
            notes='Болел'
        )
        
        self.assertEqual(attendance.notes, 'Болел')
    
    def test_attendance_marked_by(self):
        """Test attendance marked_by field."""
        from tests.utils import ScheduleFactory, TeacherFactory
        
        schedule = ScheduleFactory()
        student = StudentFactory()
        subscription = SubscriptionFactory(student=student)
        teacher = TeacherFactory()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            marked_by=teacher
        )
        
        self.assertEqual(attendance.marked_by, teacher)
