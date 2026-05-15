"""
Tests for Homework models.
"""

import pytest
from django.test import TestCase
from homework.models import Homework, HomeWorkStudents
from tests.utils import HomeworkFactory, SchoolGroupFactory, StudentFactory


@pytest.mark.unit
class HomeworkModelTest(TestCase):
    """Test cases for Homework model."""
    
    def test_homework_creation(self):
        """Test creating homework with valid data."""
        group = SchoolGroupFactory()
        
        homework = Homework.objects.create(
            task='Решить задачи 1-10 на странице 45',
            group=group
        )
        
        self.assertEqual(homework.task, 'Решить задачи 1-10 на странице 45')
        self.assertEqual(homework.group, group)
        self.assertIsNotNone(homework.created)
    
    def test_homework_str_representation(self):
        """Test string representation of homework."""
        homework = HomeworkFactory(task='Выучить таблицу умножения')
        
        str_repr = str(homework)
        self.assertIn('Задание на', str_repr)
    
    def test_homework_created_timestamp(self):
        """Test that created timestamp is set automatically."""
        homework = HomeworkFactory()
        
        self.assertIsNotNone(homework.created)
    
    def test_homework_finished_timestamp(self):
        """Test that finished timestamp is set."""
        homework = HomeworkFactory()
        
        self.assertIsNotNone(homework.finished)
    
    def test_homework_factory(self):
        """Test HomeworkFactory creates valid homework."""
        homework = HomeworkFactory()
        
        self.assertIsNotNone(homework.id)
        self.assertIsNotNone(homework.task)
        self.assertIsNotNone(homework.group)
    
    def test_multiple_homework_for_group(self):
        """Test creating multiple homework assignments for same group."""
        group = SchoolGroupFactory()
        
        hw1 = Homework.objects.create(task='Задание 1', group=group)
        hw2 = Homework.objects.create(task='Задание 2', group=group)
        hw3 = Homework.objects.create(task='Задание 3', group=group)
        
        group_homework = Homework.objects.filter(group=group)
        self.assertEqual(group_homework.count(), 3)
    
    def test_homework_deletion(self):
        """Test deleting homework."""
        homework = HomeworkFactory()
        homework_id = homework.id
        
        homework.delete()
        
        self.assertFalse(Homework.objects.filter(id=homework_id).exists())


@pytest.mark.unit
class HomeWorkStudentsModelTest(TestCase):
    """Test cases for HomeWorkStudents model."""
    
    def test_homework_student_assignment(self):
        """Test assigning homework to student."""
        student = StudentFactory()
        homework = HomeworkFactory()
        
        assignment = HomeWorkStudents.objects.create(
            student=student,
            homework=homework
        )
        
        self.assertEqual(assignment.student, student)
        self.assertEqual(assignment.homework, homework)
    
    def test_homework_assigned_to_multiple_students(self):
        """Test assigning same homework to multiple students."""
        homework = HomeworkFactory()
        student1 = StudentFactory()
        student2 = StudentFactory()
        student3 = StudentFactory()
        
        HomeWorkStudents.objects.create(student=student1, homework=homework)
        HomeWorkStudents.objects.create(student=student2, homework=homework)
        HomeWorkStudents.objects.create(student=student3, homework=homework)
        
        assignments = HomeWorkStudents.objects.filter(homework=homework)
        self.assertEqual(assignments.count(), 3)
    
    def test_student_with_multiple_homework(self):
        """Test student with multiple homework assignments."""
        student = StudentFactory()
        hw1 = HomeworkFactory()
        hw2 = HomeworkFactory()
        hw3 = HomeworkFactory()
        
        HomeWorkStudents.objects.create(student=student, homework=hw1)
        HomeWorkStudents.objects.create(student=student, homework=hw2)
        HomeWorkStudents.objects.create(student=student, homework=hw3)
        
        student_homework = HomeWorkStudents.objects.filter(student=student)
        self.assertEqual(student_homework.count(), 3)
    
    def test_get_students_for_homework(self):
        """Test getting all students assigned to homework."""
        homework = HomeworkFactory()
        student1 = StudentFactory()
        student2 = StudentFactory()
        
        HomeWorkStudents.objects.create(student=student1, homework=homework)
        HomeWorkStudents.objects.create(student=student2, homework=homework)
        
        assignments = HomeWorkStudents.objects.filter(homework=homework)
        student_ids = [a.student.id for a in assignments]
        
        self.assertIn(student1.id, student_ids)
        self.assertIn(student2.id, student_ids)
    
    def test_get_homework_for_student(self):
        """Test getting all homework for student."""
        student = StudentFactory()
        hw1 = HomeworkFactory()
        hw2 = HomeworkFactory()
        
        HomeWorkStudents.objects.create(student=student, homework=hw1)
        HomeWorkStudents.objects.create(student=student, homework=hw2)
        
        assignments = HomeWorkStudents.objects.filter(student=student)
        homework_ids = [a.homework.id for a in assignments]
        
        self.assertIn(hw1.id, homework_ids)
        self.assertIn(hw2.id, homework_ids)
    
    def test_delete_homework_assignment(self):
        """Test deleting homework assignment."""
        student = StudentFactory()
        homework = HomeworkFactory()
        
        assignment = HomeWorkStudents.objects.create(
            student=student,
            homework=homework
        )
        assignment_id = assignment.id
        
        assignment.delete()
        
        self.assertFalse(HomeWorkStudents.objects.filter(id=assignment_id).exists())
    
    def test_cascade_delete_on_homework_deletion(self):
        """Test that assignments are deleted when homework is deleted."""
        homework = HomeworkFactory()
        student1 = StudentFactory()
        student2 = StudentFactory()
        
        HomeWorkStudents.objects.create(student=student1, homework=homework)
        HomeWorkStudents.objects.create(student=student2, homework=homework)
        
        homework_id = homework.id
        homework.delete()
        
        # All assignments should be deleted
        self.assertEqual(
            HomeWorkStudents.objects.filter(homework_id=homework_id).count(),
            0
        )
    
    def test_cascade_delete_on_student_deletion(self):
        """Test that assignments are deleted when student is deleted."""
        student = StudentFactory()
        hw1 = HomeworkFactory()
        hw2 = HomeworkFactory()
        
        HomeWorkStudents.objects.create(student=student, homework=hw1)
        HomeWorkStudents.objects.create(student=student, homework=hw2)
        
        student_id = student.id
        student.delete()
        
        # All assignments should be deleted
        self.assertEqual(
            HomeWorkStudents.objects.filter(student_id=student_id).count(),
            0
        )
