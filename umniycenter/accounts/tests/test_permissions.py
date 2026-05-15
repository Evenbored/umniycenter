"""
Tests for Accounts permissions.
"""

import pytest
from django.test import TestCase, RequestFactory
from rest_framework.test import APIRequestFactory
from accounts.permissions import (
    IsAdminRole, IsTeacherRole, IsStudentRole,
    IsAdminOrTeacherRole, IsAdminTeacherOrStudentRole
)
from tests.utils import AdminFactory, TeacherFactory, StudentFactory, ParentFactory


@pytest.mark.unit
class IsAdminRoleTest(TestCase):
    """Test cases for IsAdminRole permission."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsAdminRole()
    
    def test_admin_has_permission(self):
        """Test that admin user has permission."""
        admin = AdminFactory()
        request = self.factory.get('/')
        request.user = admin
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_teacher_no_permission(self):
        """Test that teacher user has no permission."""
        teacher = TeacherFactory()
        request = self.factory.get('/')
        request.user = teacher
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_student_no_permission(self):
        """Test that student user has no permission."""
        student = StudentFactory()
        request = self.factory.get('/')
        request.user = student
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_parent_no_permission(self):
        """Test that parent user has no permission."""
        parent = ParentFactory()
        request = self.factory.get('/')
        request.user = parent
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_unauthenticated_no_permission(self):
        """Test that unauthenticated user has no permission."""
        from django.contrib.auth.models import AnonymousUser
        
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        self.assertFalse(self.permission.has_permission(request, None))


@pytest.mark.unit
class IsTeacherRoleTest(TestCase):
    """Test cases for IsTeacherRole permission."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsTeacherRole()
    
    def test_teacher_has_permission(self):
        """Test that teacher user has permission."""
        teacher = TeacherFactory()
        request = self.factory.get('/')
        request.user = teacher
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_admin_no_permission(self):
        """Test that admin user has no permission."""
        admin = AdminFactory()
        request = self.factory.get('/')
        request.user = admin
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_student_no_permission(self):
        """Test that student user has no permission."""
        student = StudentFactory()
        request = self.factory.get('/')
        request.user = student
        
        self.assertFalse(self.permission.has_permission(request, None))


@pytest.mark.unit
class IsStudentRoleTest(TestCase):
    """Test cases for IsStudentRole permission."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsStudentRole()
    
    def test_student_has_permission(self):
        """Test that student user has permission."""
        student = StudentFactory()
        request = self.factory.get('/')
        request.user = student
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_teacher_no_permission(self):
        """Test that teacher user has no permission."""
        teacher = TeacherFactory()
        request = self.factory.get('/')
        request.user = teacher
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_admin_no_permission(self):
        """Test that admin user has no permission."""
        admin = AdminFactory()
        request = self.factory.get('/')
        request.user = admin
        
        self.assertFalse(self.permission.has_permission(request, None))


@pytest.mark.unit
class IsAdminOrTeacherRoleTest(TestCase):
    """Test cases for IsAdminOrTeacherRole permission."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsAdminOrTeacherRole()
    
    def test_admin_has_permission(self):
        """Test that admin user has permission."""
        admin = AdminFactory()
        request = self.factory.get('/')
        request.user = admin
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_teacher_has_permission(self):
        """Test that teacher user has permission."""
        teacher = TeacherFactory()
        request = self.factory.get('/')
        request.user = teacher
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_student_no_permission(self):
        """Test that student user has no permission."""
        student = StudentFactory()
        request = self.factory.get('/')
        request.user = student
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_parent_no_permission(self):
        """Test that parent user has no permission."""
        parent = ParentFactory()
        request = self.factory.get('/')
        request.user = parent
        
        self.assertFalse(self.permission.has_permission(request, None))


@pytest.mark.unit
class IsAdminTeacherOrStudentRoleTest(TestCase):
    """Test cases for IsAdminTeacherOrStudentRole permission."""
    
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsAdminTeacherOrStudentRole()
    
    def test_admin_has_permission(self):
        """Test that admin user has permission."""
        admin = AdminFactory()
        request = self.factory.get('/')
        request.user = admin
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_teacher_has_permission(self):
        """Test that teacher user has permission."""
        teacher = TeacherFactory()
        request = self.factory.get('/')
        request.user = teacher
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_student_has_permission(self):
        """Test that student user has permission."""
        student = StudentFactory()
        request = self.factory.get('/')
        request.user = student
        
        self.assertTrue(self.permission.has_permission(request, None))
    
    def test_parent_no_permission(self):
        """Test that parent user has no permission."""
        parent = ParentFactory()
        request = self.factory.get('/')
        request.user = parent
        
        self.assertFalse(self.permission.has_permission(request, None))
    
    def test_unauthenticated_no_permission(self):
        """Test that unauthenticated user has no permission."""
        from django.contrib.auth.models import AnonymousUser
        
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        self.assertFalse(self.permission.has_permission(request, None))
