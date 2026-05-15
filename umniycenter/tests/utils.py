"""
Test utilities and factories for Django tests.

This module provides:
- Factory classes for creating test data
- Helper functions for common test operations
- Mock objects for external services
- Configured API client that bypasses middleware
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from rest_framework.test import APIClient

fake = Faker('ru_RU')
User = get_user_model()


# ============================================================================
# CONFIGURED API CLIENT
# ============================================================================

def get_api_client():
    """
    Get configured APIClient that bypasses ApiAjaxOnlyMiddleware.
    
    The middleware requires one of:
    - X-Requested-With: XMLHttpRequest
    - Accept: application/json
    - Content-Type: application/json
    """
    client = APIClient()
    # Set default headers to bypass middleware
    client.default_format = 'json'
    # Add the Accept header that the middleware checks for
    client.credentials(HTTP_ACCEPT='application/json')
    return client


# ============================================================================
# USER FACTORIES
# ============================================================================

class UserFactory(DjangoModelFactory):
    """Factory for creating CustomUser instances."""
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    first_name = factory.Faker('first_name', locale='ru_RU')
    last_name = factory.Faker('last_name', locale='ru_RU')
    phone = factory.LazyFunction(lambda: f'+7{fake.msisdn()[3:13]}')
    is_active = True
    sex = True  # Male by default
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password after user creation."""
        if create:
            password = extracted if extracted else 'testpass123'
            obj.set_password(password)
            obj.save()


class AdminFactory(UserFactory):
    """Factory for creating admin users."""
    role = 2  # ADMIN
    is_staff = True
    is_superuser = True


class TeacherFactory(UserFactory):
    """Factory for creating teacher users."""
    role = 0  # TEACHER


class StudentFactory(UserFactory):
    """Factory for creating student users."""
    role = 1  # STUDENT


class ParentFactory(UserFactory):
    """Factory for creating parent users."""
    role = 3  # PARENT


# ============================================================================
# COURSE FACTORIES
# ============================================================================

class CourseFactory(DjangoModelFactory):
    """Factory for creating Course instances."""
    
    class Meta:
        model = 'courses.Courses'
        django_get_or_create = ('name',)
    
    name = factory.Sequence(lambda n: f'Course {n}')


# ============================================================================
# GROUP FACTORIES
# ============================================================================

class SchoolGroupFactory(DjangoModelFactory):
    """Factory for creating SchoolGroup instances."""
    
    class Meta:
        model = 'groups.SchoolGroups'
        django_get_or_create = ('number',)
    
    number = factory.Sequence(lambda n: f'Group-{n}')
    course = factory.SubFactory(CourseFactory)
    teacher = factory.SubFactory(TeacherFactory)
    is_active = True


# ============================================================================
# SUBSCRIPTION FACTORIES
# ============================================================================

class TariffFactory(DjangoModelFactory):
    """Factory for creating Tariff instances."""
    
    class Meta:
        model = 'subscriptions.Tariff'
    
    name = factory.Sequence(lambda n: f'Tariff {n}')
    course = factory.SubFactory(CourseFactory)
    lessons_count = 8
    validity_days = 30
    price = Decimal('5000.00')
    description = factory.Faker('text', max_nb_chars=200, locale='ru_RU')
    is_active = True
    is_trial = False


class SubscriptionFactory(DjangoModelFactory):
    """Factory for creating Subscription instances."""
    
    class Meta:
        model = 'subscriptions.Subscription'
    
    student = factory.SubFactory(StudentFactory)
    parent = factory.SubFactory(ParentFactory)
    tariff = factory.SubFactory(TariffFactory)
    lessons_total = factory.LazyAttribute(lambda obj: obj.tariff.lessons_count)
    lessons_used = 0
    start_date = factory.LazyFunction(lambda: timezone.now().date())
    end_date = factory.LazyAttribute(
        lambda obj: obj.start_date + timedelta(days=obj.tariff.validity_days)
    )
    status = 'active'


class PaymentFactory(DjangoModelFactory):
    """Factory for creating Payment instances."""
    
    class Meta:
        model = 'subscriptions.Payment'
    
    subscription = factory.SubFactory(SubscriptionFactory)
    parent = factory.LazyAttribute(lambda obj: obj.subscription.parent)
    amount = factory.LazyAttribute(lambda obj: obj.subscription.tariff.price)
    payment_method = 'cash'
    status = 'pending'


# ============================================================================
# SCHEDULE FACTORIES
# ============================================================================

class ScheduleFactory(DjangoModelFactory):
    """Factory for creating Schedule instances."""
    
    class Meta:
        model = 'schedule.Schedule'
    
    group = factory.SubFactory(SchoolGroupFactory)
    teacher = factory.LazyAttribute(lambda obj: obj.group.teacher)
    classdateStart = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=1, hours=10)
    )
    classdateEnd = factory.LazyAttribute(
        lambda obj: (obj.classdateStart + timedelta(minutes=45)).time()
    )
    status = 'scheduled'


class GroupScheduleTemplateFactory(DjangoModelFactory):
    """Factory for creating GroupScheduleTemplate instances."""
    
    class Meta:
        model = 'schedule.GroupScheduleTemplate'
    
    group = factory.SubFactory(SchoolGroupFactory)
    weekday = 1  # Monday
    start_time = factory.LazyFunction(lambda: timezone.now().replace(hour=10, minute=0, second=0, microsecond=0).time())
    lessons_count = 1
    is_active = True


# ============================================================================
# HOMEWORK FACTORIES
# ============================================================================

class HomeworkFactory(DjangoModelFactory):
    """Factory for creating Homework instances."""
    
    class Meta:
        model = 'homework.Homework'
    
    task = factory.Faker('sentence', nb_words=10, locale='ru_RU')
    group = factory.SubFactory(SchoolGroupFactory)


# ============================================================================
# MAIN APP FACTORIES
# ============================================================================

class ParticipantRequestFactory(DjangoModelFactory):
    """Factory for creating ParticipantRequest instances."""
    
    class Meta:
        model = 'main.ParticipantRequest'
    
    parent_fio = factory.Faker('name', locale='ru_RU')
    child_fio = factory.Faker('name', locale='ru_RU')
    phone = factory.LazyFunction(lambda: f'+7{fake.msisdn()[3:13]}')
    age = factory.Faker('random_int', min=5, max=17)
    source = 'internet'
    checked = False
    
    @factory.post_generation
    def courses(obj, create, extracted, **kwargs):
        """Add courses to the request."""
        if not create:
            return
        
        if extracted:
            for course in extracted:
                obj.courses.add(course)
        else:
            # Add one random course by default
            course = CourseFactory()
            obj.courses.add(course)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_student_with_parent():
    """
    Create a student with associated parent and profiles.
    
    Returns:
        tuple: (student_user, parent_user)
    """
    from accounts.models import StudentProfile, ParentProfile
    
    parent = ParentFactory()
    student = StudentFactory()
    
    # Create profiles
    student_profile, _ = StudentProfile.objects.get_or_create(user=student)
    parent_profile, _ = ParentProfile.objects.get_or_create(user=parent)
    
    # Link parent to student
    parent_profile.students.add(student_profile)
    
    return student, parent


def create_student_with_subscription(status='active'):
    """
    Create a student with parent and active subscription.
    
    Args:
        status: Subscription status (default: 'active')
    
    Returns:
        tuple: (student, parent, subscription)
    """
    student, parent = create_student_with_parent()
    
    subscription = SubscriptionFactory(
        student=student,
        parent=parent,
        status=status
    )
    
    return student, parent, subscription


def create_group_with_students(student_count=3):
    """
    Create a group with specified number of students.
    
    Args:
        student_count: Number of students to add (default: 3)
    
    Returns:
        tuple: (group, list of students)
    """
    from students.models import StudentGroups
    
    group = SchoolGroupFactory()
    students = []
    
    for _ in range(student_count):
        student, _ = create_student_with_parent()
        StudentGroups.objects.create(group=group, student=student)
        students.append(student)
    
    return group, students


def create_schedule_with_attendance(student_count=3):
    """
    Create a schedule with students and mark attendance.
    
    Args:
        student_count: Number of students (default: 3)
    
    Returns:
        tuple: (schedule, list of students, list of attendance records)
    """
    from subscriptions.models import LessonAttendance
    
    group, students = create_group_with_students(student_count)
    schedule = ScheduleFactory(group=group)
    
    attendance_records = []
    for student in students:
        _, _, subscription = create_student_with_subscription()
        subscription.student = student
        subscription.save()
        
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            subscription=subscription,
            status='present',
            lessons_count=1,
            lesson_deducted=True
        )
        attendance_records.append(attendance)
    
    return schedule, students, attendance_records


# ============================================================================
# MOCK OBJECTS FOR EXTERNAL SERVICES
# ============================================================================

class MockYooKassa:
    """Mock YooKassa payment gateway responses."""
    
    @staticmethod
    def create_payment_success(payment_id='test_payment_123', amount='5000.00'):
        """Mock successful payment creation."""
        return {
            'id': payment_id,
            'status': 'pending',
            'amount': {
                'value': amount,
                'currency': 'RUB'
            },
            'confirmation': {
                'type': 'redirect',
                'confirmation_url': f'https://test.yookassa.ru/payments/{payment_id}'
            },
            'created_at': timezone.now().isoformat(),
            'paid': False,
            'test': True
        }
    
    @staticmethod
    def webhook_payment_succeeded(payment_id='test_payment_123', amount='5000.00'):
        """Mock successful payment webhook."""
        return {
            'type': 'notification',
            'event': 'payment.succeeded',
            'object': {
                'id': payment_id,
                'status': 'succeeded',
                'amount': {
                    'value': amount,
                    'currency': 'RUB'
                },
                'paid': True,
                'created_at': timezone.now().isoformat(),
                'captured_at': timezone.now().isoformat(),
                'test': True
            }
        }
    
    @staticmethod
    def webhook_payment_canceled(payment_id='test_payment_123', amount='5000.00'):
        """Mock canceled payment webhook."""
        return {
            'type': 'notification',
            'event': 'payment.canceled',
            'object': {
                'id': payment_id,
                'status': 'canceled',
                'amount': {
                    'value': amount,
                    'currency': 'RUB'
                },
                'paid': False,
                'created_at': timezone.now().isoformat(),
                'canceled_at': timezone.now().isoformat(),
                'test': True
            }
        }
    
    @staticmethod
    def webhook_payment_waiting_for_capture(payment_id='test_payment_123', amount='5000.00'):
        """Mock payment waiting for capture webhook."""
        return {
            'type': 'notification',
            'event': 'payment.waiting_for_capture',
            'object': {
                'id': payment_id,
                'status': 'waiting_for_capture',
                'amount': {
                    'value': amount,
                    'currency': 'RUB'
                },
                'paid': True,
                'created_at': timezone.now().isoformat(),
                'test': True
            }
        }


# ============================================================================
# ASSERTION HELPERS
# ============================================================================

def assert_user_has_role(user, expected_role):
    """Assert that user has expected role."""
    role_names = {0: 'TEACHER', 1: 'STUDENT', 2: 'ADMIN', 3: 'PARENT'}
    assert user.role == expected_role, (
        f"Expected user role {role_names.get(expected_role)}, "
        f"got {role_names.get(user.role)}"
    )


def assert_subscription_valid(subscription):
    """Assert that subscription is valid and active."""
    assert subscription.is_valid, "Subscription should be valid"
    assert subscription.status == 'active', "Subscription should be active"
    assert subscription.lessons_remaining > 0, "Subscription should have remaining lessons"


def assert_payment_completed(payment):
    """Assert that payment is completed."""
    assert payment.status == 'completed', f"Payment status should be 'completed', got '{payment.status}'"
    assert payment.paid_at is not None, "Payment should have paid_at timestamp"


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================

def generate_valid_phone():
    """Generate valid Russian phone number in +7XXXXXXXXXX format."""
    return f'+7{fake.msisdn()[3:13]}'


def generate_invalid_phones():
    """Generate list of invalid phone numbers for testing."""
    return [
        '89001234567',  # Missing +7
        '+7900123456',  # Too short
        '+79001234567890',  # Too long
        '+79001234abc',  # Contains letters
        '8-900-123-45-67',  # Wrong format
        '+7 900 123 45 67',  # Contains spaces
        '',  # Empty
        None,  # None
    ]
