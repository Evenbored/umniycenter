"""
Tests for Accounts views.
"""

import pytest
from django.test import TestCase, Client
from django.urls import include, path, reverse
from django.test import override_settings
from django.contrib.auth import get_user_model
from tests.utils import UserFactory, StudentFactory, TeacherFactory

User = get_user_model()


TEST_TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': False,
        'OPTIONS': {
            'loaders': [
                (
                    'django.template.loaders.locmem.Loader',
                    {
                        'users/trainer_base.html': (
                            '<html><head><title>{% block title %}{% endblock %}</title></head>'
                            '<body>{% block content %}{% endblock %}</body></html>'
                        ),
                    },
                ),
                'django.template.loaders.app_directories.Loader',
            ],
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]


urlpatterns = [
    path('api/v1/', include('umniycenter.api_urls', namespace='api')),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('users/', include(('accounts.urls', 'accounts'), namespace='users')),
    path('homework/', include(('homework.urls', 'homework'), namespace='homework')),
    path('students/', include(('students.urls', 'students'), namespace='students')),
    path('groups/', include(('groups.urls', 'groups'), namespace='groups')),
]


@pytest.mark.integration
@override_settings(TEMPLATES=TEST_TEMPLATES, ROOT_URLCONF=__name__)
class RegisterViewTest(TestCase):
    """Test cases for user registration view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:register')
    
    def test_register_page_loads(self):
        """Test that registration page loads successfully."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
    
    def test_register_with_valid_data(self):
        """Test registration with valid data."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'phone': '+79001234567',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        
        response = self.client.post(self.url, data=form_data)
        
        # Should redirect after successful registration
        self.assertEqual(response.status_code, 302)
        
        # User should be created
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_register_with_duplicate_username(self):
        """Test registration with existing username."""
        UserFactory(username='existinguser')
        
        form_data = {
            'username': 'existinguser',
            'email': 'new@test.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'phone': '+79001234567',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        
        response = self.client.post(self.url, data=form_data)
        
        # Should stay on registration page with errors
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)


@pytest.mark.integration
@override_settings(ROOT_URLCONF=__name__)
class LoginViewTest(TestCase):
    """Test cases for login view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:login')
        self.user = UserFactory(username='testuser', password='testpass123')
    
    def test_login_page_loads(self):
        """Test that login page loads successfully."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
    
    def test_login_with_valid_credentials(self):
        """Test login with valid credentials."""
        response = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'testpass123',
        })
        
        # Should redirect after successful login
        self.assertEqual(response.status_code, 302)
        
        # User should be authenticated
        self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_login_with_invalid_password(self):
        """Test login with invalid password."""
        response = self.client.post(self.url, {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        
        # Should stay on login page
        self.assertEqual(response.status_code, 200)
        
        # User should not be authenticated
        self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_login_with_nonexistent_user(self):
        """Test login with nonexistent user."""
        response = self.client.post(self.url, {
            'username': 'nonexistent',
            'password': 'somepassword',
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


@pytest.mark.integration
class LogoutViewTest(TestCase):
    """Test cases for logout view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:logout')
        self.user = UserFactory(username='testuser', password='testpass123')
    
    def test_logout_authenticated_user(self):
        """Test logout for authenticated user."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.url)
        
        # Should redirect after logout
        self.assertEqual(response.status_code, 302)


@pytest.mark.integration
@override_settings(ROOT_URLCONF=__name__)
class ProfileViewTest(TestCase):
    """Test cases for profile view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:profile')
    
    def test_profile_requires_authentication(self):
        """Test that profile page requires authentication."""
        response = self.client.get(self.url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_profile_loads_for_authenticated_user(self):
        """Test that profile page loads for authenticated user."""
        user = UserFactory(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, user.username)
    
    def test_student_profile_shows_schedule(self):
        """Test that student profile shows schedule."""
        student = StudentFactory(username='student1', password='testpass123')
        self.client.login(username='student1', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_teacher_profile_shows_schedule(self):
        """Test that teacher profile shows schedule."""
        teacher = TeacherFactory(username='teacher1', password='testpass123')
        self.client.login(username='teacher1', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.integration
@override_settings(ROOT_URLCONF=__name__)
class AccountDetailsViewTest(TestCase):
    """Test cases for account details view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:account_details')
        self.user = UserFactory(username='testuser', password='testpass123')
    
    def test_account_details_requires_authentication(self):
        """Test that account details requires authentication."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_account_details_loads(self):
        """Test that account details page loads."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.first_name)
        self.assertContains(response, self.user.last_name)


@pytest.mark.integration
@override_settings(ROOT_URLCONF=__name__)
class UpdateAccountDetailsViewTest(TestCase):
    """Test cases for update account details view."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:update_account_details')
        self.user = UserFactory(
            username='testuser',
            password='testpass123',
            first_name='Старое',
            last_name='Имя'
        )
    
    def test_update_account_requires_authentication(self):
        """Test that update requires authentication."""
        response = self.client.post(self.url, {})
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_update_account_with_valid_data(self):
        """Test updating account with valid data."""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.url, {
            'first_name': 'Новое',
            'last_name': 'Имя',
            'email': 'newemail@test.com',
            'phone': self.user.phone or '+79001234567',
            'username': self.user.username,
            'sex': self.user.sex,
        })
        
        # Should return 200 with updated account details partial
        self.assertEqual(response.status_code, 200)
        
        # User data should be updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Новое')
        self.assertEqual(self.user.email, 'newemail@test.com')
