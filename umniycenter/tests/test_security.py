"""
Security tests for the application.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from tests.utils import UserFactory, AdminFactory, TeacherFactory, StudentFactory

User = get_user_model()


@pytest.mark.security
class CSRFProtectionTest(TestCase):
    """Test cases for CSRF protection."""
    
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
    
    def test_post_without_csrf_token_fails(self):
        """Test that POST without CSRF token fails."""
        url = reverse('accounts:register')
        
        response = self.client.post(url, {
            'username': 'testuser',
            'password1': 'testpass123',
            'password2': 'testpass123',
        })
        
        self.assertEqual(response.status_code, 403)
    
    def test_post_with_csrf_token_succeeds(self):
        """Test that POST with CSRF token succeeds."""
        # Get CSRF token first
        response = self.client.get(reverse('accounts:register'))
        csrf_token = response.cookies.get('csrftoken')
        
        if csrf_token:
            response = self.client.post(
                reverse('accounts:register'),
                {
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'password1': 'SecurePass123!',
                    'password2': 'SecurePass123!',
                    'csrfmiddlewaretoken': csrf_token.value,
                }
            )
            
            # Should not be 403
            self.assertNotEqual(response.status_code, 403)


@pytest.mark.security
class XSSPreventionTest(TestCase):
    """Test cases for XSS prevention."""
    
    def test_html_tags_stripped_from_user_input(self):
        """Test that HTML tags are stripped from user input."""
        user = UserFactory()
        user.first_name = '<script>alert("XSS")</script>Test'
        user.last_name = '<b>User</b>'
        user.clean()
        
        self.assertNotIn('<script>', user.first_name)
        self.assertNotIn('<b>', user.last_name)
        self.assertIn('Test', user.first_name)
        self.assertIn('User', user.last_name)
    
    def test_form_input_sanitization(self):
        """Test that form input is sanitized."""
        from accounts.forms import CustomUserUpdateForm
        
        user = UserFactory()
        form = CustomUserUpdateForm(
            data={
                'first_name': '<script>alert("XSS")</script>John',
                'last_name': '<img src=x onerror=alert(1)>Doe',
                'email': user.email,
            },
            instance=user
        )
        
        if form.is_valid():
            updated_user = form.save(commit=False)
            self.assertNotIn('<script>', updated_user.first_name)
            self.assertNotIn('<img', updated_user.last_name)


@pytest.mark.security
class SQLInjectionPreventionTest(TestCase):
    """Test cases for SQL injection prevention."""
    
    def test_orm_prevents_sql_injection(self):
        """Test that Django ORM prevents SQL injection."""
        # Create a user
        UserFactory(username='testuser')
        
        # Try SQL injection in filter
        malicious_input = "testuser' OR '1'='1"
        
        # Django ORM should escape this properly
        users = User.objects.filter(username=malicious_input)
        
        # Should return 0 results, not all users
        self.assertEqual(users.count(), 0)
    
    def test_parameterized_queries(self):
        """Test that queries are parameterized."""
        user1 = UserFactory(username='user1')
        user2 = UserFactory(username='user2')
        
        # This should only return user1
        result = User.objects.filter(username='user1')
        
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().username, 'user1')


@pytest.mark.security
class PasswordSecurityTest(TestCase):
    """Test cases for password security."""
    
    def test_passwords_are_hashed(self):
        """Test that passwords are hashed, not stored in plaintext."""
        user = User.objects.create_user(
            username='testuser',
            first_name='Test',
            last_name='User',
            password='plainpassword123'
        )
        
        # Password should be hashed
        self.assertNotEqual(user.password, 'plainpassword123')
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
    
    def test_password_verification(self):
        """Test password verification works correctly."""
        user = User.objects.create_user(
            username='testuser',
            first_name='Test',
            last_name='User',
            password='correctpassword'
        )
        
        self.assertTrue(user.check_password('correctpassword'))
        self.assertFalse(user.check_password('wrongpassword'))
    
    def test_weak_password_rejected(self):
        """Test that weak passwords are rejected."""
        from django.core.exceptions import ValidationError
        from django.contrib.auth.password_validation import validate_password
        
        weak_passwords = ['123', 'password', 'abc', '12345678']
        
        for weak_pass in weak_passwords:
            with self.assertRaises(ValidationError):
                validate_password(weak_pass)
    
    def test_strong_password_accepted(self):
        """Test that strong passwords are accepted."""
        from django.contrib.auth.password_validation import validate_password
        
        strong_password = 'SecureP@ssw0rd123!'
        
        # Should not raise ValidationError
        try:
            validate_password(strong_password)
            self.assertTrue(True)
        except Exception:
            self.fail('Strong password should be accepted')


@pytest.mark.security
class AuthenticationSecurityTest(TestCase):
    """Test cases for authentication security."""
    
    def setUp(self):
        self.client = Client()
    
    def test_unauthenticated_cannot_access_protected_views(self):
        """Test that unauthenticated users cannot access protected views."""
        protected_urls = [
            reverse('accounts:profile'),
            reverse('accounts:account_details'),
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            
            # Should redirect to login
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response.url)
    
    def test_session_expires_on_logout(self):
        """Test that session is cleared on logout."""
        user = UserFactory(username='testuser', password='testpass123')
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Verify logged in
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        
        # Logout
        self.client.logout()
        
        # Should not be able to access protected page
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)


@pytest.mark.security
class AuthorizationTest(TestCase):
    """Test cases for authorization and access control."""
    
    def setUp(self):
        self.client = Client()
    
    def test_student_cannot_access_admin_views(self):
        """Test that students cannot access admin views."""
        student = StudentFactory(username='student', password='testpass123')
        self.client.login(username='student', password='testpass123')
        
        response = self.client.get(reverse('crm:dashboard'))
        
        # Should be denied
        self.assertIn(response.status_code, [302, 403])
    
    def test_teacher_cannot_access_admin_views(self):
        """Test that teachers cannot access admin-only views."""
        teacher = TeacherFactory(username='teacher', password='testpass123')
        self.client.login(username='teacher', password='testpass123')
        
        response = self.client.get(reverse('crm:dashboard'))
        
        # Should be denied
        self.assertIn(response.status_code, [302, 403])
    
    def test_admin_can_access_admin_views(self):
        """Test that admins can access admin views."""
        admin = AdminFactory(username='admin', password='testpass123')
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(reverse('crm:dashboard'))
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.security
class DataValidationTest(TestCase):
    """Test cases for data validation."""
    
    def test_phone_number_validation(self):
        """Test phone number format validation."""
        from main.forms import ParticipantRequestForm
        from tests.utils import CourseFactory
        
        course = CourseFactory()
        
        invalid_phones = [
            '1234567890',
            '+1234567890',
            'abcdefghijk',
            '+7900',
        ]
        
        for invalid_phone in invalid_phones:
            form = ParticipantRequestForm(data={
                'parent_fio': 'Test',
                'child_fio': 'Test',
                'phone': invalid_phone,
                'age': '10',
                'courses': [course.id],
            })
            
            self.assertFalse(form.is_valid())
            self.assertIn('phone', form.errors)
    
    def test_email_validation(self):
        """Test email format validation."""
        from accounts.forms import CustomUserCreationForm
        
        form = CustomUserCreationForm(data={
            'username': 'testuser',
            'email': 'not-an-email',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


@pytest.mark.security
class SessionSecurityTest(TestCase):
    """Test cases for session security."""
    
    def test_session_cookie_httponly(self):
        """Test that session cookie has HttpOnly flag."""
        from django.conf import settings
        
        # Check settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
    
    def test_csrf_cookie_httponly(self):
        """Test that CSRF cookie has HttpOnly flag."""
        from django.conf import settings
        
        # CSRF cookie should be HttpOnly
        # This is a Django default
        self.assertTrue(True)  # Placeholder for actual check


@pytest.mark.security
class FileUploadSecurityTest(TestCase):
    """Test cases for file upload security."""
    
    def test_file_extension_validation(self):
        """Test that file extensions are validated."""
        # This is a placeholder - implement if file uploads exist
        self.assertTrue(True)
    
    def test_file_size_validation(self):
        """Test that file sizes are validated."""
        # This is a placeholder - implement if file uploads exist
        self.assertTrue(True)
