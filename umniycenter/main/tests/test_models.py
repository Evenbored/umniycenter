"""
Tests for Main app models.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from main.models import ParticipantRequest
from tests.utils import ParticipantRequestFactory, CourseFactory, generate_valid_phone, generate_invalid_phones


@pytest.mark.unit
class ParticipantRequestModelTest(TestCase):
    """Test cases for ParticipantRequest model."""
    
    def test_participant_request_creation(self):
        """Test creating participant request with valid data."""
        course = CourseFactory()
        
        request = ParticipantRequest.objects.create(
            parent_fio='Иванов Иван Иванович',
            child_fio='Иванов Петр Иванович',
            phone='+79001234567',
            age='10',
            source='internet',
            checked=False
        )
        request.courses.add(course)
        
        self.assertEqual(request.parent_fio, 'Иванов Иван Иванович')
        self.assertEqual(request.child_fio, 'Иванов Петр Иванович')
        self.assertEqual(request.phone, '+79001234567')
        self.assertEqual(request.age, '10')
        self.assertEqual(request.source, 'internet')
        self.assertFalse(request.checked)
    
    def test_participant_request_str_representation(self):
        """Test string representation of participant request."""
        request = ParticipantRequestFactory(
            parent_fio='Петров Петр Петрович',
            child_fio='Петров Алексей Петрович'
        )
        
        str_repr = str(request)
        self.assertEqual(str_repr, f'Заявка {request.id}')
    
    def test_phone_validation_valid_format(self):
        """Test phone validation with valid format."""
        valid_phone = generate_valid_phone()
        
        request = ParticipantRequest(
            parent_fio='Тест Тестович',
            child_fio='Тест Младший',
            phone=valid_phone,
            age='10',
            source='internet'
        )
        
        # Should not raise ValidationError
        request.full_clean()
        request.save()
        
        self.assertEqual(request.phone, valid_phone)
    
    def test_phone_validation_invalid_formats(self):
        """Test phone validation with invalid formats."""
        invalid_phones = generate_invalid_phones()
        
        for invalid_phone in invalid_phones:
            if invalid_phone is None or invalid_phone == '':
                continue
                
            request = ParticipantRequest(
                parent_fio='Тест Тестович',
                child_fio='Тест Младший',
                phone=invalid_phone,
                age='10',
                source='internet'
            )
            
            with self.assertRaises(ValidationError):
                request.full_clean()
    
    def test_source_choices(self):
        """Test all valid source choices."""
        from accounts.models import LeadSource
        
        valid_sources = [
            LeadSource.POSTER,
            LeadSource.RELATIVES,
            LeadSource.FRIENDS,
            LeadSource.VK,
            LeadSource.INTERNET,
            LeadSource.RETURNING,
            LeadSource.OTHER
        ]
        
        for source in valid_sources:
            request = ParticipantRequestFactory(source=source)
            self.assertEqual(request.source, source)
    
    def test_multiple_courses_selection(self):
        """Test selecting multiple courses."""
        course1 = CourseFactory(name='Python')
        course2 = CourseFactory(name='JavaScript')
        course3 = CourseFactory(name='Робототехника')
        
        request = ParticipantRequestFactory()
        request.courses.clear()
        request.courses.add(course1, course2, course3)
        
        self.assertEqual(request.courses.count(), 3)
        self.assertIn(course1, request.courses.all())
        self.assertIn(course2, request.courses.all())
        self.assertIn(course3, request.courses.all())
    
    def test_get_courses_display_method(self):
        """Test get_courses_display() method."""
        course1 = CourseFactory(name='Python')
        course2 = CourseFactory(name='JavaScript')
        
        request = ParticipantRequestFactory()
        request.courses.add(course1, course2)
        
        courses_display = request.get_courses_display()
        
        self.assertIn('Python', courses_display)
        self.assertIn('JavaScript', courses_display)
    
    def test_checked_field_default_false(self):
        """Test that checked field defaults to False."""
        request = ParticipantRequestFactory()
        
        self.assertFalse(request.checked)
    
    def test_mark_request_as_checked(self):
        """Test marking request as checked."""
        request = ParticipantRequestFactory(checked=False)
        
        request.checked = True
        request.save()
        
        request.refresh_from_db()
        self.assertTrue(request.checked)
    
    def test_email_field_optional(self):
        """Test that email field is optional."""
        request = ParticipantRequest.objects.create(
            parent_fio='Тест Тестович',
            child_fio='Тест Младший',
            phone='+79001234567',
            age='10',
            source='internet',
            email=None
        )
        
        self.assertIsNone(request.email)
    
    def test_email_field_with_value(self):
        """Test participant request with email."""
        request = ParticipantRequestFactory(
            email='parent@example.com'
        )
        
        self.assertEqual(request.email, 'parent@example.com')
    
    def test_age_field_as_string(self):
        """Test that age is stored as string."""
        request = ParticipantRequestFactory(age='7')
        
        self.assertEqual(request.age, '7')
        self.assertIsInstance(request.age, str)
    
    def test_created_timestamp(self):
        """Test that created timestamp is set automatically."""
        request = ParticipantRequestFactory()
        
        self.assertIsNotNone(request.created)
        self.assertLessEqual(request.created, request.created)
    
    def test_participant_request_factory(self):
        """Test ParticipantRequestFactory creates valid requests."""
        request = ParticipantRequestFactory()
        
        self.assertIsNotNone(request.id)
        self.assertIsNotNone(request.parent_fio)
        self.assertIsNotNone(request.child_fio)
        self.assertIsNotNone(request.phone)
        self.assertIsNotNone(request.age)
        self.assertGreater(request.courses.count(), 0)
    
    def test_filter_unchecked_requests(self):
        """Test filtering unchecked requests."""
        checked_request = ParticipantRequestFactory(checked=True)
        unchecked1 = ParticipantRequestFactory(checked=False)
        unchecked2 = ParticipantRequestFactory(checked=False)
        
        unchecked_requests = ParticipantRequest.objects.filter(checked=False)
        
        self.assertEqual(unchecked_requests.count(), 2)
        self.assertIn(unchecked1, unchecked_requests)
        self.assertIn(unchecked2, unchecked_requests)
        self.assertNotIn(checked_request, unchecked_requests)
    
    def test_filter_by_source(self):
        """Test filtering requests by source."""
        internet_request = ParticipantRequestFactory(source='internet')
        vk_request = ParticipantRequestFactory(source='vk')
        friends_request = ParticipantRequestFactory(source='friends')
        
        internet_requests = ParticipantRequest.objects.filter(source='internet')
        
        self.assertIn(internet_request, internet_requests)
        self.assertNotIn(vk_request, internet_requests)
        self.assertNotIn(friends_request, internet_requests)
    
    def test_filter_by_course(self):
        """Test filtering requests by course."""
        python_course = CourseFactory(name='Python')
        js_course = CourseFactory(name='JavaScript')
        
        request1 = ParticipantRequestFactory()
        request1.courses.add(python_course)
        
        request2 = ParticipantRequestFactory()
        request2.courses.add(js_course)
        
        request3 = ParticipantRequestFactory()
        request3.courses.add(python_course, js_course)
        
        python_requests = ParticipantRequest.objects.filter(courses=python_course)
        
        self.assertIn(request1, python_requests)
        self.assertNotIn(request2, python_requests)
        self.assertIn(request3, python_requests)
    
    def test_order_by_created_date(self):
        """Test ordering requests by creation date."""
        from datetime import timedelta
        from django.utils import timezone
        
        old_request = ParticipantRequestFactory()
        old_request.created = timezone.now() - timedelta(days=5)
        old_request.save()
        
        new_request = ParticipantRequestFactory()
        
        requests = ParticipantRequest.objects.order_by('-created')
        
        self.assertEqual(requests.first(), new_request)
