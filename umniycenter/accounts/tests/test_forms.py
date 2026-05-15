"""
Tests for Accounts forms.
"""

import pytest
from django.test import TestCase
from accounts.forms import CustomUserCreationForm, CustomUserLoginForm, CustomUserUpdateForm
from tests.utils import UserFactory, generate_valid_phone


@pytest.mark.unit
class CustomUserCreationFormTest(TestCase):
    """Test cases for CustomUserCreationForm."""
    
    def test_valid_registration_form(self):
        """Test form with valid data."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'phone': generate_valid_phone(),
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        form = CustomUserCreationForm(data=form_data)
        
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_password_mismatch(self):
        """Test form with mismatched passwords."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass456!',
        }
        form = CustomUserCreationForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_weak_password(self):
        """Test form with weak password."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'password1': '123',
            'password2': '123',
        }
        form = CustomUserCreationForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
    
    def test_duplicate_username(self):
        """Test form with existing username."""
        UserFactory(username='existinguser')
        
        form_data = {
            'username': 'existinguser',
            'email': 'new@test.com',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        form = CustomUserCreationForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_missing_required_fields(self):
        """Test form with missing required fields."""
        form_data = {
            'username': 'newuser',
            # Missing other required fields
        }
        form = CustomUserCreationForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)
        self.assertIn('password2', form.errors)
    
    def test_invalid_email(self):
        """Test form with invalid email."""
        form_data = {
            'username': 'newuser',
            'email': 'invalid-email',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        form = CustomUserCreationForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


@pytest.mark.unit
class CustomUserLoginFormTest(TestCase):
    """Test cases for CustomUserLoginForm."""
    
    def test_valid_login_form(self):
        """Test form with valid credentials."""
        user = UserFactory(username='testuser', password='testpass123')
        
        form_data = {
            'username': 'testuser',
            'password': 'testpass123',
        }
        form = CustomUserLoginForm(data=form_data)
        
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_invalid_credentials(self):
        """Test form with invalid credentials."""
        UserFactory(username='testuser', password='testpass123')
        
        form_data = {
            'username': 'testuser',
            'password': 'wrongpassword',
        }
        form = CustomUserLoginForm(data=form_data)
        
        self.assertFalse(form.is_valid())
    
    def test_nonexistent_user(self):
        """Test form with nonexistent user."""
        form_data = {
            'username': 'nonexistent',
            'password': 'somepassword',
        }
        form = CustomUserLoginForm(data=form_data)
        
        self.assertFalse(form.is_valid())
    
    def test_missing_username(self):
        """Test form with missing username."""
        form_data = {
            'password': 'testpass123',
        }
        form = CustomUserLoginForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_missing_password(self):
        """Test form with missing password."""
        form_data = {
            'username': 'testuser',
        }
        form = CustomUserLoginForm(data=form_data)
        
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)


@pytest.mark.unit
class CustomUserUpdateFormTest(TestCase):
    """Test cases for CustomUserUpdateForm."""
    
    def test_valid_update_form(self):
        """Test form with valid update data."""
        user = UserFactory()
        
        form_data = {
            'first_name': 'Новое Имя',
            'last_name': 'Новая Фамилия',
            'email': 'newemail@test.com',
            'phone': generate_valid_phone(),
            'address': 'Новый адрес',
            'city': 'Москва',
            'country': 'Россия',
            'sex': user.sex,
            'username': user.username,
        }
        form = CustomUserUpdateForm(data=form_data, instance=user)
        
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_html_stripping(self):
        """Test that HTML tags are stripped from input."""
        user = UserFactory()
        
        form_data = {
            'first_name': '<script>alert("XSS")</script>Иван',
            'last_name': '<b>Иванов</b>',
            'email': user.email,
        }
        form = CustomUserUpdateForm(data=form_data, instance=user)
        
        if form.is_valid():
            updated_user = form.save(commit=False)
            self.assertNotIn('<script>', updated_user.first_name)
            self.assertNotIn('<b>', updated_user.last_name)
    
    def test_email_uniqueness(self):
        """Test that email must be unique."""
        user1 = UserFactory(email='user1@test.com')
        user2 = UserFactory(email='user2@test.com')
        
        form_data = {
            'first_name': user2.first_name,
            'last_name': user2.last_name,
            'email': 'user1@test.com',  # Already taken
        }
        form = CustomUserUpdateForm(data=form_data, instance=user2)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_partial_update(self):
        """Test updating only some fields."""
        user = UserFactory(first_name='Старое', last_name='Имя')
        
        form_data = {
            'first_name': 'Новое',
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'username': user.username,
            'sex': user.sex,
        }
        form = CustomUserUpdateForm(data=form_data, instance=user)
        
        self.assertTrue(form.is_valid(), form.errors)
        updated_user = form.save()
        self.assertEqual(updated_user.first_name, 'Новое')
        self.assertEqual(updated_user.last_name, 'Имя')
    
    def test_invalid_email_format(self):
        """Test form with invalid email format."""
        user = UserFactory()
        
        form_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': 'not-an-email',
        }
        form = CustomUserUpdateForm(data=form_data, instance=user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
