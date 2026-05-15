"""
Tests for Main app forms.
"""

import pytest
from django.test import TestCase
from main.forms import ParticipantRequestForm
from tests.utils import CourseFactory, generate_valid_phone, generate_invalid_phones


@pytest.mark.unit
class ParticipantRequestFormTest(TestCase):
    """Test cases for ParticipantRequestForm."""
    
    def test_valid_form_data(self):
        """Test form with valid data."""
        course = CourseFactory()
        
        form_data = {
            'parent_fio': 'Иванов Иван Иванович',
            'child_fio': 'Иванов Петр Иванович',
            'phone': '+79001234567',
            'age': '10',
            'courses': [course.id],
            'source': 'internet',
        }
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_phone_validation_valid_format(self):
        """Test phone validation with valid format."""
        course = CourseFactory()
        valid_phone = generate_valid_phone()
        
        form_data = {
            'parent_fio': 'Тест Тестович',
            'child_fio': 'Тест Младший',
            'phone': valid_phone,
            'age': '8',
            'courses': [course.id],
            'source': 'internet',
        }
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_phone_validation_invalid_format(self):
        """Test phone validation with invalid format."""
        course = CourseFactory()
        
        invalid_phones = [
            '89001234567',  # Missing +7
            '+7900123456',  # Too short
            '+79001234567890',  # Too long
            '8-900-123-45-67',  # Wrong format
        ]
        
        for invalid_phone in invalid_phones:
            form_data = {
                'parent_fio': 'Тест Тестович',
                'child_fio': 'Тест Младший',
                'phone': invalid_phone,
                'age': '8',
                'courses': [course.id],
                'source': 'internet',
            }
            
            form = ParticipantRequestForm(data=form_data)
            
            self.assertFalse(form.is_valid())
            self.assertIn('phone', form.errors)
    
    def test_phone_starts_with_plus_seven(self):
        """Test that phone must start with +7."""
        course = CourseFactory()
        
        form_data = {
            'parent_fio': 'Тест Тестович',
            'child_fio': 'Тест Младший',
            'phone': '89001234567',  # Starts with 8, not +7
            'age': '8',
            'courses': [course.id],
            'source': 'internet',
        }
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)
    
    def test_phone_exactly_12_characters(self):
        """Test that phone must be exactly 12 characters."""
        course = CourseFactory()
        
        # Too short
        form_data = {
            'parent_fio': 'Тест Тестович',
            'child_fio': 'Тест Младший',
            'phone': '+790012345',  # Only 11 chars
            'age': '8',
            'courses': [course.id],
            'source': 'internet',
        }
        
        form = ParticipantRequestForm(data=form_data)
        self.assertFalse(form.is_valid())
    
    def test_required_fields(self):
        """Test that required fields are validated."""
        form_data = {}
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('parent_fio', form.errors)
        self.assertIn('child_fio', form.errors)
        self.assertIn('phone', form.errors)
        self.assertIn('age', form.errors)
        self.assertIn('courses', form.errors)
    
    def test_source_field_optional(self):
        """Test that source field is optional."""
        course = CourseFactory()
        
        form_data = {
            'parent_fio': 'Тест Тестович',
            'child_fio': 'Тест Младший',
            'phone': '+79001234567',
            'age': '8',
            'courses': [course.id],
            # source not provided
        }
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_multiple_courses_selection(self):
        """Test selecting multiple courses."""
        course1 = CourseFactory(name='Python')
        course2 = CourseFactory(name='JavaScript')
        course3 = CourseFactory(name='Робототехника')
        
        form_data = {
            'parent_fio': 'Тест Тестович',
            'child_fio': 'Тест Младший',
            'phone': '+79001234567',
            'age': '10',
            'courses': [course1.id, course2.id, course3.id],
            'source': 'internet',
        }
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertTrue(form.is_valid(), form.errors)
        
        if form.is_valid():
            instance = form.save()
            self.assertEqual(instance.courses.count(), 3)
    
    def test_source_choices(self):
        """Test all valid source choices."""
        course = CourseFactory()
        
        valid_sources = ['poster', 'relatives', 'friends', 'vk', 'internet', 'returning', 'other']
        
        for source in valid_sources:
            form_data = {
                'parent_fio': 'Тест Тестович',
                'child_fio': 'Тест Младший',
                'phone': '+79001234567',
                'age': '8',
                'courses': [course.id],
                'source': source,
            }
            
            form = ParticipantRequestForm(data=form_data)
            
            self.assertTrue(form.is_valid(), f"Source '{source}' should be valid. Errors: {form.errors}")
    
    def test_age_field_validation(self):
        """Test age field accepts string values."""
        course = CourseFactory()
        
        valid_ages = ['5', '7', '10', '15', '17']
        
        for age in valid_ages:
            form_data = {
                'parent_fio': 'Тест Тестович',
                'child_fio': 'Тест Младший',
                'phone': '+79001234567',
                'age': age,
                'courses': [course.id],
                'source': 'internet',
            }
            
            form = ParticipantRequestForm(data=form_data)
            
            self.assertTrue(form.is_valid(), f"Age '{age}' should be valid. Errors: {form.errors}")
    
    def test_form_save(self):
        """Test saving form creates ParticipantRequest."""
        course = CourseFactory()
        
        form_data = {
            'parent_fio': 'Сидоров Сидор Сидорович',
            'child_fio': 'Сидоров Алексей Сидорович',
            'phone': '+79001234567',
            'age': '12',
            'courses': [course.id],
            'source': 'vk',
        }
        
        form = ParticipantRequestForm(data=form_data)
        
        self.assertTrue(form.is_valid())
        
        instance = form.save()
        
        self.assertEqual(instance.parent_fio, 'Сидоров Сидор Сидорович')
        self.assertEqual(instance.child_fio, 'Сидоров Алексей Сидорович')
        self.assertEqual(instance.phone, '+79001234567')
        self.assertEqual(instance.age, '12')
        self.assertEqual(instance.source, 'vk')
        self.assertIn(course, instance.courses.all())
    
    def test_form_widgets_have_correct_classes(self):
        """Test that form widgets have correct CSS classes."""
        form = ParticipantRequestForm()
        
        # Check that fields have 'form-control border-0' class
        self.assertIn('form-control border-0', form.fields['parent_fio'].widget.attrs.get('class', ''))
        self.assertIn('form-control border-0', form.fields['child_fio'].widget.attrs.get('class', ''))
        self.assertIn('form-control border-0', form.fields['phone'].widget.attrs.get('class', ''))
        self.assertIn('form-control border-0', form.fields['age'].widget.attrs.get('class', ''))
        self.assertIn('form-select border-0', form.fields['source'].widget.attrs.get('class', ''))
    
    def test_form_placeholders(self):
        """Test that form fields have correct placeholders."""
        form = ParticipantRequestForm()
        
        self.assertEqual(
            form.fields['parent_fio'].widget.attrs.get('placeholder'),
            'Иванов Иван Иванович'
        )
        self.assertEqual(
            form.fields['child_fio'].widget.attrs.get('placeholder'),
            'Иванов Петр Иванович'
        )
        self.assertEqual(
            form.fields['phone'].widget.attrs.get('placeholder'),
            '+79001234567'
        )
    
    def test_phone_pattern_attribute(self):
        """Test that phone field has pattern attribute."""
        form = ParticipantRequestForm()
        
        pattern = form.fields['phone'].widget.attrs.get('pattern')
        self.assertIsNotNone(pattern)
        self.assertIn(r'\+7\d{10}', pattern)
    
    def test_age_min_max_attributes(self):
        """Test that age field has min and max attributes."""
        form = ParticipantRequestForm()
        
        self.assertEqual(form.fields['age'].widget.attrs.get('min'), '1')
        self.assertEqual(form.fields['age'].widget.attrs.get('max'), '18')
