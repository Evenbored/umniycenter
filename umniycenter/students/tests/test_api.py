"""
Tests for Students API views.
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from accounts.models import StudentProfile, ParentProfile
from students.models import StudentGroups
from tests.utils import (
    AdminFactory, TeacherFactory, StudentFactory, ParentFactory,
    SchoolGroupFactory, create_student_with_parent, generate_valid_phone,
    get_api_client
)


@pytest.mark.api
class MyStudentsAPIViewTest(TestCase):
    """Test cases for MyStudentsAPIView."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:my_students')
    
    def test_admin_sees_all_students(self):
        """Test that admin sees all students."""
        admin = AdminFactory()
        student1 = StudentFactory()
        student2 = StudentFactory()
        student3 = StudentFactory()
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_ids = [s['student'] for s in response.data]
        
        self.assertIn(student1.id, student_ids)
        self.assertIn(student2.id, student_ids)
        self.assertIn(student3.id, student_ids)
    
    def test_teacher_sees_only_their_students(self):
        """Test that teacher sees only students in their groups."""
        teacher = TeacherFactory()
        other_teacher = TeacherFactory()
        
        my_group = SchoolGroupFactory(teacher=teacher)
        other_group = SchoolGroupFactory(teacher=other_teacher)
        
        my_student = StudentFactory()
        other_student = StudentFactory()
        
        StudentGroups.objects.create(student=my_student, group=my_group)
        StudentGroups.objects.create(student=other_student, group=other_group)
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_ids = [s['student'] for s in response.data]
        
        self.assertIn(my_student.id, student_ids)
        self.assertNotIn(other_student.id, student_ids)
    
    def test_student_sees_only_themselves(self):
        """Test that student sees only their own data."""
        student = StudentFactory()
        other_student = StudentFactory()
        
        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_ids = [s['id'] for s in response.data]
        
        self.assertEqual(len(student_ids), 0)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_filter_students_by_search(self):
        """Test filtering students by search query."""
        admin = AdminFactory()
        student1 = StudentFactory(first_name='Иван', last_name='Иванов')
        student2 = StudentFactory(first_name='Петр', last_name='Петров')
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url, {'search': 'Иван'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_ids = [s['student'] for s in response.data]
        
        self.assertIn(student1.id, student_ids)
        self.assertNotIn(student2.id, student_ids)
    
    def test_students_response_structure(self):
        """Test that response has correct structure."""
        admin = AdminFactory()
        student = StudentFactory()
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if len(response.data) > 0:
            student_data = response.data[0]
            self.assertIn('student', student_data)
            self.assertIn('student_details', student_data)
            self.assertIn('id', student_data['student_details'])
            self.assertIn('username', student_data['student_details'])
            self.assertIn('first_name', student_data['student_details'])
            self.assertIn('last_name', student_data['student_details'])


@pytest.mark.api
class CreateStudentAPIViewTest(TestCase):
    """Test cases for creating students."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:create_student')
    
    def test_admin_can_create_student_with_new_parent(self):
        """Test that admin can create student with new parent."""
        admin = AdminFactory()
        
        data = {
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'username': 'ivan_student',
            'sex': '1',
            'parent_first_name': 'Петр',
            'parent_last_name': 'Иванов',
            'parent_phone': generate_valid_phone(),
            'parent_email': 'parent@test.com',
        }
        
        self.client.force_authenticate(user=admin)
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify student was created
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.assertTrue(User.objects.filter(username='ivan_student').exists())
    
    def test_admin_can_create_student_with_existing_parent(self):
        """Test creating student with existing parent."""
        admin = AdminFactory()
        parent = ParentFactory()
        
        data = {
            'first_name': 'Мария',
            'last_name': 'Петрова',
            'username': 'maria_student',
            'sex': '0',
            'parent_first_name': parent.first_name,
            'parent_last_name': parent.last_name,
            'parent_phone': parent.phone,
        }
        
        self.client.force_authenticate(user=admin)
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_auto_generate_parent_username(self):
        """Test that parent username is auto-generated if not provided."""
        admin = AdminFactory()
        
        data = {
            'first_name': 'Анна',
            'last_name': 'Сидорова',
            'username': 'anna_student',
            'sex': '1',
            'parent_first_name': 'Ольга',
            'parent_last_name': 'Сидорова',
            'parent_phone': generate_valid_phone(),
        }
        
        self.client.force_authenticate(user=admin)
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Parent should be created with auto-generated username
        from django.contrib.auth import get_user_model
        User = get_user_model()
        parent = User.objects.filter(first_name='Ольга', last_name='Сидорова', role=3).first()
        self.assertIsNotNone(parent)
        self.assertTrue(parent.username.startswith('parent_'))
    
    def test_teacher_cannot_create_student(self):
        """Test that teacher cannot create student."""
        teacher = TeacherFactory()
        
        data = {
            'first_name': 'Тест',
            'last_name': 'Тестов',
            'username': 'test_student',
            'sex': '1',
            'parent_first_name': 'Родитель',
            'parent_last_name': 'Тестов',
            'parent_phone': generate_valid_phone(),
        }
        
        self.client.force_authenticate(user=teacher)
        response = self.client.post(self.url, data)
        
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_201_CREATED])
    
    def test_unauthenticated_cannot_create_student(self):
        """Test that unauthenticated users cannot create student."""
        data = {
            'first_name': 'Тест',
            'last_name': 'Тестов',
            'username': 'test_student',
            'sex': '1',
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_student_with_invalid_data(self):
        """Test creating student with invalid data."""
        admin = AdminFactory()
        
        data = {
            'first_name': '',  # Empty
            'last_name': 'Тестов',
            'username': 'test_student',
            'sex': '1',
        }
        
        self.client.force_authenticate(user=admin)
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.api
class UpdateStudentAPIViewTest(TestCase):
    """Test cases for updating student details."""
    
    def setUp(self):
        self.client = get_api_client()
    
    def test_admin_can_update_student(self):
        """Test that admin can update student details."""
        admin = AdminFactory()
        student = StudentFactory(first_name='Старое')
        url = reverse('api:update_student', kwargs={'student_id': student.id})
        
        data = {'first_name': 'Новое'}
        
        self.client.force_authenticate(user=admin)
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        student.refresh_from_db()
        self.assertEqual(student.first_name, 'Новое')
    
    def test_update_student_phone(self):
        """Test updating student phone."""
        admin = AdminFactory()
        student = StudentFactory()
        url = reverse('api:update_student', kwargs={'student_id': student.id})
        
        new_phone = generate_valid_phone()
        data = {'phone': new_phone}
        
        self.client.force_authenticate(user=admin)
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        student.refresh_from_db()
        self.assertEqual(student.phone, new_phone)
    
    def test_unauthenticated_cannot_update(self):
        """Test that unauthenticated users cannot update."""
        student = StudentFactory()
        url = reverse('api:update_student', kwargs={'student_id': student.id})
        
        response = self.client.patch(url, {'first_name': 'Новое'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.api
class AddStudentToGroupAPIViewTest(TestCase):
    """Test cases for adding student to group."""
    
    def setUp(self):
        self.client = get_api_client()
    
    def test_admin_can_add_student_to_group(self):
        """Test that admin can add student to group."""
        admin = AdminFactory()
        student = StudentFactory()
        group = SchoolGroupFactory()
        url = reverse('api:add_student_to_group', kwargs={'student_id': student.id})
        
        data = {'group_id': group.id}
        
        self.client.force_authenticate(user=admin)
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify student was added to group
        self.assertTrue(StudentGroups.objects.filter(student=student, group=group).exists())
    
    def test_cannot_add_student_to_same_group_twice(self):
        """Test that student cannot be added to same group twice."""
        admin = AdminFactory()
        student = StudentFactory()
        group = SchoolGroupFactory()
        url = reverse('api:add_student_to_group', kwargs={'student_id': student.id})
        
        StudentGroups.objects.create(student=student, group=group)
        
        data = {'group_id': group.id}
        
        self.client.force_authenticate(user=admin)
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_add_student_to_multiple_groups(self):
        """Test adding student to multiple groups."""
        admin = AdminFactory()
        student = StudentFactory()
        group1 = SchoolGroupFactory()
        group2 = SchoolGroupFactory()
        url = reverse('api:add_student_to_group', kwargs={'student_id': student.id})
        
        self.client.force_authenticate(user=admin)
        
        response1 = self.client.post(url, {'group_id': group1.id})
        response2 = self.client.post(url, {'group_id': group2.id})
        
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        self.assertEqual(StudentGroups.objects.filter(student=student).count(), 2)


@pytest.mark.api
class RemoveStudentFromGroupAPIViewTest(TestCase):
    """Test cases for removing student from group."""
    
    def setUp(self):
        self.client = get_api_client()
    
    def test_admin_can_remove_student_from_group(self):
        """Test that admin can remove student from group."""
        admin = AdminFactory()
        student = StudentFactory()
        group = SchoolGroupFactory()
        
        membership = StudentGroups.objects.create(student=student, group=group)
        url = reverse('api:remove_student_from_group', kwargs={
            'student_id': student.id,
            'membership_id': membership.id
        })
        
        self.client.force_authenticate(user=admin)
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify student was removed from group
        self.assertFalse(StudentGroups.objects.filter(id=membership.id).exists())
    
    def test_remove_nonexistent_membership(self):
        """Test removing nonexistent membership."""
        admin = AdminFactory()
        student = StudentFactory()
        url = reverse('api:remove_student_from_group', kwargs={
            'student_id': student.id,
            'membership_id': 99999
        })
        
        self.client.force_authenticate(user=admin)
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@pytest.mark.api
class StudentsCountAPIViewTest(TestCase):
    """Test cases for students count API."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:students_count')
    
    def test_admin_gets_total_students_count(self):
        """Test that admin gets total students count."""
        admin = AdminFactory()
        group = SchoolGroupFactory()
        students = [StudentFactory(), StudentFactory(), StudentFactory()]
        for student in students:
            StudentGroups.objects.create(student=student, group=group)
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
    
    def test_teacher_gets_their_students_count(self):
        """Test that teacher gets count of their students."""
        teacher = TeacherFactory()
        group = SchoolGroupFactory(teacher=teacher)
        
        student1 = StudentFactory()
        student2 = StudentFactory()
        StudentGroups.objects.create(student=student1, group=group)
        StudentGroups.objects.create(student=student2, group=group)
        
        # Other student not in teacher's group
        StudentFactory()
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
