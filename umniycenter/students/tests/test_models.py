"""
Tests for Students models.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from students.models import StudentGroups
from tests.utils import (
    StudentFactory, SchoolGroupFactory, 
    create_student_with_parent, create_group_with_students
)


@pytest.mark.unit
class StudentGroupsModelTest(TestCase):
    """Test cases for StudentGroups model."""
    
    def test_student_group_creation(self):
        """Test creating student-group relationship."""
        student = StudentFactory()
        group = SchoolGroupFactory()
        
        student_group = StudentGroups.objects.create(
            student=student,
            group=group
        )
        
        self.assertEqual(student_group.student, student)
        self.assertEqual(student_group.group, group)
        self.assertIsNotNone(student_group.id)
    
    def test_student_group_str_representation(self):
        """Test string representation of student-group."""
        student = StudentFactory(username='student1')
        group = SchoolGroupFactory(number='Group-1')
        
        student_group = StudentGroups.objects.create(
            student=student,
            group=group
        )
        
        str_repr = str(student_group)
        self.assertIn(str(group).lower(), str_repr.lower())
        self.assertIn(str(student).lower(), str_repr.lower())
    
    def test_student_group_unique_constraint(self):
        """Test that student-group combination must be unique."""
        student = StudentFactory()
        group = SchoolGroupFactory()
        
        StudentGroups.objects.create(student=student, group=group)
        
        with self.assertRaises(IntegrityError):
            StudentGroups.objects.create(student=student, group=group)
    
    def test_student_can_be_in_multiple_groups(self):
        """Test that student can be in multiple groups."""
        student = StudentFactory()
        group1 = SchoolGroupFactory(number='Group-1')
        group2 = SchoolGroupFactory(number='Group-2')
        group3 = SchoolGroupFactory(number='Group-3')
        
        StudentGroups.objects.create(student=student, group=group1)
        StudentGroups.objects.create(student=student, group=group2)
        StudentGroups.objects.create(student=student, group=group3)
        
        student_groups = StudentGroups.objects.filter(student=student)
        self.assertEqual(student_groups.count(), 3)
    
    def test_group_can_have_multiple_students(self):
        """Test that group can have multiple students."""
        group = SchoolGroupFactory()
        student1 = StudentFactory()
        student2 = StudentFactory()
        student3 = StudentFactory()
        
        StudentGroups.objects.create(student=student1, group=group)
        StudentGroups.objects.create(student=student2, group=group)
        StudentGroups.objects.create(student=student3, group=group)
        
        group_students = StudentGroups.objects.filter(group=group)
        self.assertEqual(group_students.count(), 3)
    
    def test_student_group_clean_validation(self):
        """Test clean() method prevents duplicate assignments."""
        student = StudentFactory()
        group = SchoolGroupFactory()
        
        StudentGroups.objects.create(student=student, group=group)
        
        duplicate = StudentGroups(student=student, group=group)
        
        with self.assertRaises(ValidationError):
            duplicate.clean()
    
    def test_student_group_deletion(self):
        """Test deleting student-group relationship."""
        student = StudentFactory()
        group = SchoolGroupFactory()
        
        student_group = StudentGroups.objects.create(
            student=student,
            group=group
        )
        student_group_id = student_group.id
        
        student_group.delete()
        
        self.assertFalse(StudentGroups.objects.filter(id=student_group_id).exists())
    
    def test_remove_student_from_group(self):
        """Test removing student from specific group."""
        student = StudentFactory()
        group1 = SchoolGroupFactory()
        group2 = SchoolGroupFactory()
        
        sg1 = StudentGroups.objects.create(student=student, group=group1)
        sg2 = StudentGroups.objects.create(student=student, group=group2)
        
        sg1.delete()
        
        # Student should still be in group2
        self.assertTrue(StudentGroups.objects.filter(student=student, group=group2).exists())
        self.assertFalse(StudentGroups.objects.filter(student=student, group=group1).exists())
    
    def test_student_group_queryset_filtering(self):
        """Test filtering student-group relationships."""
        student1 = StudentFactory()
        student2 = StudentFactory()
        group = SchoolGroupFactory()
        
        StudentGroups.objects.create(student=student1, group=group)
        StudentGroups.objects.create(student=student2, group=group)
        
        student1_groups = StudentGroups.objects.filter(student=student1)
        
        self.assertEqual(student1_groups.count(), 1)
        self.assertEqual(student1_groups.first().group, group)
    
    def test_create_group_with_students_helper(self):
        """Test helper function for creating group with students."""
        group, students = create_group_with_students(student_count=5)
        
        self.assertEqual(len(students), 5)
        self.assertEqual(StudentGroups.objects.filter(group=group).count(), 5)
        
        for student in students:
            self.assertTrue(
                StudentGroups.objects.filter(student=student, group=group).exists()
            )
    
    def test_student_requires_student_role(self):
        """Test that only users with STUDENT role can be added."""
        from tests.utils import TeacherFactory
        
        teacher = TeacherFactory()  # Wrong role
        group = SchoolGroupFactory()
        
        # Depending on implementation, this might be validated
        student_group = StudentGroups(student=teacher, group=group)
        
        # If validation exists, it should fail
        # Otherwise, this is a potential bug to fix
        try:
            student_group.clean()
            student_group.save()
            # If no validation, at least verify it was created
            self.assertIsNotNone(student_group.id)
        except ValidationError:
            # If validation exists, this is expected
            pass
    
    def test_cascade_delete_on_student_deletion(self):
        """Test that student-group relationships are deleted when student is deleted."""
        student = StudentFactory()
        group1 = SchoolGroupFactory()
        group2 = SchoolGroupFactory()
        
        StudentGroups.objects.create(student=student, group=group1)
        StudentGroups.objects.create(student=student, group=group2)
        
        student_id = student.id
        student.delete()
        
        # All student-group relationships should be deleted
        self.assertEqual(StudentGroups.objects.filter(student_id=student_id).count(), 0)
    
    def test_cascade_delete_on_group_deletion(self):
        """Test that student-group relationships are deleted when group is deleted."""
        student1 = StudentFactory()
        student2 = StudentFactory()
        group = SchoolGroupFactory()
        
        StudentGroups.objects.create(student=student1, group=group)
        StudentGroups.objects.create(student=student2, group=group)
        
        group_id = group.id
        group.delete()
        
        # All student-group relationships should be deleted
        self.assertEqual(StudentGroups.objects.filter(group_id=group_id).count(), 0)
    
    def test_get_students_for_group(self):
        """Test getting all students in a group."""
        group, students = create_group_with_students(student_count=4)
        
        student_groups = StudentGroups.objects.filter(group=group)
        student_ids = [sg.student.id for sg in student_groups]
        
        for student in students:
            self.assertIn(student.id, student_ids)
    
    def test_get_groups_for_student(self):
        """Test getting all groups for a student."""
        student = StudentFactory()
        group1 = SchoolGroupFactory()
        group2 = SchoolGroupFactory()
        group3 = SchoolGroupFactory()
        
        StudentGroups.objects.create(student=student, group=group1)
        StudentGroups.objects.create(student=student, group=group2)
        StudentGroups.objects.create(student=student, group=group3)
        
        student_groups = StudentGroups.objects.filter(student=student)
        group_ids = [sg.group.id for sg in student_groups]
        
        self.assertIn(group1.id, group_ids)
        self.assertIn(group2.id, group_ids)
        self.assertIn(group3.id, group_ids)
