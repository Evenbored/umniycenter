"""
Tests for Courses models.
"""

import pytest
from django.test import TestCase
from django.db import IntegrityError, transaction
from courses.models import Courses
from tests.utils import CourseFactory


@pytest.mark.unit
class CoursesModelTest(TestCase):
    """Test cases for Courses model."""
    
    def test_course_creation(self):
        """Test creating a course with valid data."""
        course = Courses.objects.create(name="Python Programming")
        
        self.assertEqual(course.name, "Python Programming")
        self.assertIsNotNone(course.id)
    
    def test_course_str_representation(self):
        """Test string representation of course."""
        course = Courses.objects.create(name="Web Development")
        
        self.assertEqual(str(course), "Web Development")
    
    def test_course_name_uniqueness(self):
        """Test that course names must be unique."""
        Courses.objects.create(name="Mathematics")
        
        # PostgreSQL marks the current transaction as broken after an
        # IntegrityError.  Keep the expected error inside an inner atomic block
        # so the TestCase transaction remains usable for the following tests.
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Courses.objects.create(name="Mathematics")
    
    def test_course_name_required(self):
        """Test that course name is required."""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Courses.objects.create(name=None)
    
    def test_course_name_max_length(self):
        """Test course name max length validation."""
        long_name = "A" * 256  # Assuming max_length is 255
        
        with self.assertRaises(Exception):
            Courses.objects.create(name=long_name)
    
    def test_course_factory(self):
        """Test CourseFactory creates valid courses."""
        course = CourseFactory()
        
        self.assertIsNotNone(course.id)
        self.assertIsNotNone(course.name)
        self.assertTrue(Courses.objects.filter(id=course.id).exists())
    
    def test_multiple_courses_creation(self):
        """Test creating multiple courses."""
        course1 = Courses.objects.create(name="Course 1")
        course2 = Courses.objects.create(name="Course 2")
        course3 = Courses.objects.create(name="Course 3")
        
        self.assertEqual(Courses.objects.count(), 3)
        self.assertNotEqual(course1.id, course2.id)
        self.assertNotEqual(course2.id, course3.id)
    
    def test_course_deletion(self):
        """Test deleting a course."""
        course = Courses.objects.create(name="To Delete")
        course_id = course.id
        
        course.delete()
        
        self.assertFalse(Courses.objects.filter(id=course_id).exists())
    
    def test_course_update(self):
        """Test updating course name."""
        course = Courses.objects.create(name="Old Name")
        
        course.name = "New Name"
        course.save()
        
        updated_course = Courses.objects.get(id=course.id)
        self.assertEqual(updated_course.name, "New Name")
    
    def test_course_queryset_filtering(self):
        """Test filtering courses by name."""
        Courses.objects.create(name="Python")
        Courses.objects.create(name="Java")
        Courses.objects.create(name="JavaScript")
        
        python_courses = Courses.objects.filter(name__icontains="Python")
        self.assertEqual(python_courses.count(), 1)
        
        java_courses = Courses.objects.filter(name__icontains="Java")
        self.assertEqual(java_courses.count(), 2)  # Java and JavaScript
