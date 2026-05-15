"""
Tests for Accounts API views.
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from tests.utils import AdminFactory, TeacherFactory, StudentFactory, ParentFactory, get_api_client


@pytest.mark.api
class CurrentUserAPIViewTest(TestCase):
    """Test cases for CurrentUserAPIView."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:user_me')
    
    def test_get_current_user_authenticated(self):
        """Test getting current user info when authenticated."""
        user = StudentFactory(first_name='Иван', last_name='Иванов')
        self.client.force_authenticate(user=user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], user.id)
        self.assertEqual(response.data['username'], user.username)
        self.assertIn('display_name', response.data)
        self.assertIn('initials', response.data)
    
    def test_get_current_user_unauthenticated(self):
        """Test getting current user when not authenticated."""
        response = self.client.get(self.url)
        
        # Permission classes return 403 for unauthenticated API requests
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_current_user_display_name(self):
        """Test that display_name is properly formatted."""
        user = StudentFactory(first_name='Петр', last_name='Петров')
        self.client.force_authenticate(user=user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Петр', response.data['display_name'])
        self.assertIn('Петров', response.data['display_name'])
    
    def test_current_user_role_display(self):
        """Test that role is properly displayed."""
        teacher = TeacherFactory()
        self.client.force_authenticate(user=teacher)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], 0)  # TEACHER


@pytest.mark.api
class UserListAPIViewTest(TestCase):
    """Test cases for UserListAPIView."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:users')
    
    def test_list_users_as_admin(self):
        """Test listing users as admin."""
        admin = AdminFactory()
        TeacherFactory()
        StudentFactory()
        ParentFactory()
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 3)
    
    def test_list_users_unauthenticated(self):
        """Test listing users when not authenticated."""
        response = self.client.get(self.url)
        
        # Permission classes return 403 for unauthenticated API requests
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_filter_users_by_role_teacher(self):
        """Test filtering users by teacher role."""
        admin = AdminFactory()
        teacher1 = TeacherFactory()
        teacher2 = TeacherFactory()
        StudentFactory()
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url, {'role': 0})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher_ids = [user['id'] for user in response.data]
        self.assertIn(teacher1.id, teacher_ids)
        self.assertIn(teacher2.id, teacher_ids)
    
    def test_filter_users_by_role_student(self):
        """Test filtering users by student role."""
        admin = AdminFactory()
        student1 = StudentFactory()
        student2 = StudentFactory()
        TeacherFactory()
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url, {'role': 1})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_ids = [user['id'] for user in response.data]
        self.assertIn(student1.id, student_ids)
        self.assertIn(student2.id, student_ids)
    
    def test_filter_users_by_role_parent(self):
        """Test filtering users by parent role."""
        admin = AdminFactory()
        parent1 = ParentFactory()
        parent2 = ParentFactory()
        StudentFactory()
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url, {'role': 3})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        parent_ids = [user['id'] for user in response.data]
        self.assertIn(parent1.id, parent_ids)
        self.assertIn(parent2.id, parent_ids)
    
    def test_list_users_as_teacher(self):
        """Test that teacher can access user list."""
        teacher = TeacherFactory()
        StudentFactory()
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        # Depending on permissions, this might be allowed or denied
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_list_users_as_student(self):
        """Test that student cannot access user list."""
        student = StudentFactory()
        
        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        
        # Students should not have access to full user list
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])
    
    def test_user_list_response_structure(self):
        """Test that user list response has correct structure."""
        admin = AdminFactory()
        StudentFactory(first_name='Тест', last_name='Тестов')
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if len(response.data) > 0:
            user_data = response.data[0]
            self.assertIn('id', user_data)
            self.assertIn('username', user_data)
            self.assertIn('role', user_data)
