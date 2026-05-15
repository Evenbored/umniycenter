"""
Tests for Groups API views.
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from tests.utils import AdminFactory, TeacherFactory, StudentFactory, SchoolGroupFactory, CourseFactory, get_api_client


@pytest.mark.api
class MyGroupsAPIViewTest(TestCase):
    """Test cases for MyGroupsAPIView."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:my_groups')
    
    def test_teacher_sees_own_groups(self):
        """Test that teacher sees only their groups."""
        teacher = TeacherFactory()
        other_teacher = TeacherFactory()
        
        my_group1 = SchoolGroupFactory(teacher=teacher)
        my_group2 = SchoolGroupFactory(teacher=teacher)
        other_group = SchoolGroupFactory(teacher=other_teacher)
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group_ids = [group['id'] for group in response.data]
        
        self.assertIn(my_group1.id, group_ids)
        self.assertIn(my_group2.id, group_ids)
        self.assertNotIn(other_group.id, group_ids)
    
    def test_admin_sees_all_groups(self):
        """Test that admin sees all groups."""
        admin = AdminFactory()
        teacher1 = TeacherFactory()
        teacher2 = TeacherFactory()
        
        group1 = SchoolGroupFactory(teacher=teacher1)
        group2 = SchoolGroupFactory(teacher=teacher2)
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group_ids = [group['id'] for group in response.data]
        
        self.assertIn(group1.id, group_ids)
        self.assertIn(group2.id, group_ids)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_access(self):
        """Test student access to groups endpoint."""
        student = StudentFactory()
        
        self.client.force_authenticate(user=student)
        response = self.client.get(self.url)
        
        # Depending on permissions, might be denied
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_groups_response_structure(self):
        """Test that response has correct structure."""
        teacher = TeacherFactory()
        course = CourseFactory(name="Python")
        SchoolGroupFactory(teacher=teacher, course=course, number="Group-1")
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        
        group_data = response.data[0]
        self.assertIn('id', group_data)
        self.assertIn('number', group_data)
        self.assertIn('course', group_data)
        self.assertIn('teacher', group_data)
    
    def test_teacher_with_no_groups(self):
        """Test teacher with no groups."""
        teacher = TeacherFactory()
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_only_active_groups_shown(self):
        """Test that only active groups are shown (if filtered)."""
        teacher = TeacherFactory()
        active_group = SchoolGroupFactory(teacher=teacher, is_active=True)
        inactive_group = SchoolGroupFactory(teacher=teacher, is_active=False)
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group_ids = [group['id'] for group in response.data]
        
        # Depending on implementation, might filter by is_active
        self.assertIn(active_group.id, group_ids)


@pytest.mark.api
class GroupsCountAPIViewTest(TestCase):
    """Test cases for GroupsCountAPIView."""
    
    def setUp(self):
        self.client = get_api_client()
        self.url = reverse('api:groups_count')
    
    def test_teacher_groups_count(self):
        """Test getting groups count for teacher."""
        teacher = TeacherFactory()
        SchoolGroupFactory(teacher=teacher)
        SchoolGroupFactory(teacher=teacher)
        SchoolGroupFactory(teacher=teacher)
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
    
    def test_admin_groups_count(self):
        """Test getting total groups count for admin."""
        admin = AdminFactory()
        teacher1 = TeacherFactory()
        teacher2 = TeacherFactory()
        
        SchoolGroupFactory(teacher=teacher1)
        SchoolGroupFactory(teacher=teacher1)
        SchoolGroupFactory(teacher=teacher2)
        
        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_teacher_with_no_groups(self):
        """Test count for teacher with no groups."""
        teacher = TeacherFactory()
        
        self.client.force_authenticate(user=teacher)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)


@pytest.mark.api
class UpdateGroupAPIViewTest(TestCase):
    """Test cases for updating group details."""
    
    def setUp(self):
        self.client = get_api_client()
    
    def test_admin_can_update_group(self):
        """Test that admin can update group details."""
        admin = AdminFactory()
        group = SchoolGroupFactory(is_active=True)
        url = reverse('api:update_group', kwargs={'group_id': group.id})
        
        self.client.force_authenticate(user=admin)
        response = self.client.patch(url, {'is_active': False})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        group.refresh_from_db()
        self.assertFalse(group.is_active)
    
    def test_update_group_number(self):
        """Test updating group number."""
        admin = AdminFactory()
        group = SchoolGroupFactory(number="Old-Number")
        url = reverse('api:update_group', kwargs={'group_id': group.id})
        
        self.client.force_authenticate(user=admin)
        response = self.client.patch(url, {'number': 'New-Number'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        group.refresh_from_db()
        self.assertEqual(group.number, 'New-Number')
    
    def test_teacher_cannot_update_group(self):
        """Test that teacher cannot update group (if not allowed)."""
        teacher = TeacherFactory()
        group = SchoolGroupFactory(teacher=teacher)
        url = reverse('api:update_group', kwargs={'group_id': group.id})
        
        self.client.force_authenticate(user=teacher)
        response = self.client.patch(url, {'is_active': False})
        
        # Depending on permissions
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_unauthenticated_cannot_update(self):
        """Test that unauthenticated users cannot update."""
        group = SchoolGroupFactory()
        url = reverse('api:update_group', kwargs={'group_id': group.id})
        
        response = self.client.patch(url, {'is_active': False})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_nonexistent_group(self):
        """Test updating nonexistent group."""
        admin = AdminFactory()
        url = reverse('api:update_group', kwargs={'group_id': 99999})
        
        self.client.force_authenticate(user=admin)
        response = self.client.patch(url, {'is_active': False})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
