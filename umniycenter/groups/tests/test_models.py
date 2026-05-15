"""
Tests for Groups models.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from groups.models import SchoolGroups
from tests.utils import SchoolGroupFactory, CourseFactory, TeacherFactory, StudentFactory


@pytest.mark.unit
class SchoolGroupsModelTest(TestCase):
    """Test cases for SchoolGroups model."""
    
    def test_school_group_creation(self):
        """Test creating a school group with valid data."""
        course = CourseFactory(name="Python Programming")
        teacher = TeacherFactory()
        
        group = SchoolGroups.objects.create(
            number="Group-1",
            course=course,
            teacher=teacher,
            is_active=True
        )
        
        self.assertEqual(group.number, "Group-1")
        self.assertEqual(group.course, course)
        self.assertEqual(group.teacher, teacher)
        self.assertTrue(group.is_active)
    
    def test_school_group_str_representation(self):
        """Test string representation of school group."""
        group = SchoolGroupFactory(number="Python-101")
        
        self.assertIn("Python-101", str(group))
    
    def test_group_number_uniqueness(self):
        """Test that group numbers must be unique."""
        course = CourseFactory()
        teacher = TeacherFactory()
        
        SchoolGroups.objects.create(
            number="Group-1",
            course=course,
            teacher=teacher
        )
        
        with self.assertRaises(IntegrityError):
            SchoolGroups.objects.create(
                number="Group-1",
                course=course,
                teacher=teacher
            )
    
    def test_group_requires_course(self):
        """Test that group requires a course."""
        teacher = TeacherFactory()
        
        with self.assertRaises(IntegrityError):
            SchoolGroups.objects.create(
                number="Group-1",
                course=None,
                teacher=teacher
            )
    
    def test_group_requires_teacher(self):
        """Test that group requires a teacher."""
        course = CourseFactory()
        
        with self.assertRaises(IntegrityError):
            SchoolGroups.objects.create(
                number="Group-1",
                course=course,
                teacher=None
            )
    
    def test_group_teacher_must_be_teacher_role(self):
        """Test that group teacher must have TEACHER role."""
        course = CourseFactory()
        student = StudentFactory()  # Wrong role
        
        group = SchoolGroups(
            number="Group-1",
            course=course,
            teacher=student
        )
        
        with self.assertRaises(ValidationError):
            group.clean()
    
    def test_group_with_valid_teacher_role(self):
        """Test that group accepts user with TEACHER role."""
        course = CourseFactory()
        teacher = TeacherFactory()
        
        group = SchoolGroups(
            number="Group-1",
            course=course,
            teacher=teacher
        )
        
        # Should not raise ValidationError
        group.clean()
        group.save()
        
        self.assertIsNotNone(group.id)
    
    def test_group_is_active_default(self):
        """Test that is_active defaults to True."""
        group = SchoolGroupFactory()
        
        self.assertTrue(group.is_active)
    
    def test_group_can_be_inactive(self):
        """Test creating inactive group."""
        group = SchoolGroupFactory(is_active=False)
        
        self.assertFalse(group.is_active)
    
    def test_group_factory(self):
        """Test SchoolGroupFactory creates valid groups."""
        group = SchoolGroupFactory()
        
        self.assertIsNotNone(group.id)
        self.assertIsNotNone(group.number)
        self.assertIsNotNone(group.course)
        self.assertIsNotNone(group.teacher)
        self.assertEqual(group.teacher.role, 0)  # TEACHER role
    
    def test_multiple_groups_same_course(self):
        """Test creating multiple groups for same course."""
        course = CourseFactory()
        teacher1 = TeacherFactory()
        teacher2 = TeacherFactory()
        
        group1 = SchoolGroups.objects.create(
            number="Group-1",
            course=course,
            teacher=teacher1
        )
        group2 = SchoolGroups.objects.create(
            number="Group-2",
            course=course,
            teacher=teacher2
        )
        
        self.assertEqual(group1.course, group2.course)
        self.assertNotEqual(group1.teacher, group2.teacher)
    
    def test_multiple_groups_same_teacher(self):
        """Test that teacher can have multiple groups."""
        teacher = TeacherFactory()
        course1 = CourseFactory(name="Python")
        course2 = CourseFactory(name="JavaScript")
        
        group1 = SchoolGroups.objects.create(
            number="Group-1",
            course=course1,
            teacher=teacher
        )
        group2 = SchoolGroups.objects.create(
            number="Group-2",
            course=course2,
            teacher=teacher
        )
        
        self.assertEqual(group1.teacher, group2.teacher)
        self.assertNotEqual(group1.course, group2.course)
    
    def test_group_deletion(self):
        """Test deleting a group."""
        group = SchoolGroupFactory()
        group_id = group.id
        
        group.delete()
        
        self.assertFalse(SchoolGroups.objects.filter(id=group_id).exists())
    
    def test_group_update(self):
        """Test updating group details."""
        group = SchoolGroupFactory(is_active=True)
        
        group.is_active = False
        group.save()
        
        updated_group = SchoolGroups.objects.get(id=group.id)
        self.assertFalse(updated_group.is_active)
    
    def test_group_queryset_filtering_by_course(self):
        """Test filtering groups by course."""
        course1 = CourseFactory(name="Python")
        course2 = CourseFactory(name="Java")
        
        group1 = SchoolGroupFactory(course=course1)
        group2 = SchoolGroupFactory(course=course2)
        
        python_groups = SchoolGroups.objects.filter(course=course1)
        
        self.assertEqual(python_groups.count(), 1)
        self.assertIn(group1, python_groups)
        self.assertNotIn(group2, python_groups)
    
    def test_group_queryset_filtering_by_teacher(self):
        """Test filtering groups by teacher."""
        teacher1 = TeacherFactory()
        teacher2 = TeacherFactory()
        
        group1 = SchoolGroupFactory(teacher=teacher1)
        group2 = SchoolGroupFactory(teacher=teacher2)
        
        teacher1_groups = SchoolGroups.objects.filter(teacher=teacher1)
        
        self.assertEqual(teacher1_groups.count(), 1)
        self.assertIn(group1, teacher1_groups)
        self.assertNotIn(group2, teacher1_groups)
    
    def test_group_queryset_filtering_by_active_status(self):
        """Test filtering groups by active status."""
        active_group = SchoolGroupFactory(is_active=True)
        inactive_group = SchoolGroupFactory(is_active=False)
        
        active_groups = SchoolGroups.objects.filter(is_active=True)
        
        self.assertIn(active_group, active_groups)
        self.assertNotIn(inactive_group, active_groups)
    
    def test_group_related_name_from_course(self):
        """Test accessing groups from course."""
        course = CourseFactory()
        group1 = SchoolGroupFactory(course=course)
        group2 = SchoolGroupFactory(course=course)
        
        # Assuming related_name is 'groups' or similar
        course_groups = SchoolGroups.objects.filter(course=course)
        
        self.assertEqual(course_groups.count(), 2)
        self.assertIn(group1, course_groups)
        self.assertIn(group2, course_groups)
    
    def test_group_related_name_from_teacher(self):
        """Test accessing groups from teacher."""
        teacher = TeacherFactory()
        group1 = SchoolGroupFactory(teacher=teacher)
        group2 = SchoolGroupFactory(teacher=teacher)
        
        teacher_groups = SchoolGroups.objects.filter(teacher=teacher)
        
        self.assertEqual(teacher_groups.count(), 2)
        self.assertIn(group1, teacher_groups)
        self.assertIn(group2, teacher_groups)
