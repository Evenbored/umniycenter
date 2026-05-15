"""
Tests for CRM views.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from tests.utils import AdminFactory, TeacherFactory, StudentFactory


@pytest.mark.integration
class CRMDashboardViewTest(TestCase):
    """Test cases for CRM dashboard view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:dashboard')
    
    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_dashboard(self):
        """Test that admin can access dashboard."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_teacher_cannot_access_dashboard(self):
        """Test that teacher cannot access dashboard."""
        teacher = TeacherFactory(username='teacher', password='testpass123')
        self.client.login(username='teacher', password='testpass123')
        
        response = self.client.get(self.url)
        
        # Should be denied or redirected
        self.assertIn(response.status_code, [302, 403])
    
    def test_student_cannot_access_dashboard(self):
        """Test that student cannot access dashboard."""
        student = StudentFactory(username='student', password='testpass123')
        self.client.login(username='student', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertIn(response.status_code, [302, 403])


@pytest.mark.integration
class CRMRequestsViewTest(TestCase):
    """Test cases for CRM requests view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:requests')
    
    def test_requests_view_requires_authentication(self):
        """Test that requests view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_requests_view(self):
        """Test that admin can access requests view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class CRMStudentsViewTest(TestCase):
    """Test cases for CRM students view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:students')
    
    def test_students_view_requires_authentication(self):
        """Test that students view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_students_view(self):
        """Test that admin can access students view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class CRMParentsViewTest(TestCase):
    """Test cases for CRM parents view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:parents')
    
    def test_parents_view_requires_authentication(self):
        """Test that parents view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_parents_view(self):
        """Test that admin can access parents view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class CRMPaymentsViewTest(TestCase):
    """Test cases for CRM payments view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:payments')
    
    def test_payments_view_requires_authentication(self):
        """Test that payments view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_payments_view(self):
        """Test that admin can access payments view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class CRMGroupsViewTest(TestCase):
    """Test cases for CRM groups view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:groups')
    
    def test_groups_view_requires_authentication(self):
        """Test that groups view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_groups_view(self):
        """Test that admin can access groups view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class CRMTariffsViewTest(TestCase):
    """Test cases for CRM tariffs view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:tariffs')
    
    def test_tariffs_view_requires_authentication(self):
        """Test that tariffs view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_tariffs_view(self):
        """Test that admin can access tariffs view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
class CRMScheduleViewTest(TestCase):
    """Test cases for CRM schedule view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('crm:schedule')
    
    def test_schedule_view_requires_authentication(self):
        """Test that schedule view requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_can_access_schedule_view(self):
        """Test that admin can access schedule view."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
