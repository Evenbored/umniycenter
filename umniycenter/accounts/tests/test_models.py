"""
Tests for Accounts models.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from accounts.models import (
    CustomUser, UserRole, TeacherProfile, StudentProfile, 
    ParentProfile, LeadSource
)
from tests.utils import (
    UserFactory, AdminFactory, TeacherFactory, 
    StudentFactory, ParentFactory, assert_user_has_role
)

User = get_user_model()


@pytest.mark.unit
class CustomUserModelTest(TestCase):
    """Test cases for CustomUser model."""
    
    def test_create_user_with_username(self):
        """Test creating a user with username."""
        user = User.objects.create_user(
            username='testuser',
            first_name='Test',
            last_name='User',
            password='testpass123',
            email='test@example.com'
        )
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
    
    def test_create_superuser(self):
        """Test creating a superuser."""
        admin = User.objects.create_superuser(
            username='admin',
            first_name='Admin',
            last_name='User',
            password='adminpass123',
            email='admin@example.com'
        )
        
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
    
    def test_user_str_representation(self):
        """Test string representation of user."""
        user = UserFactory(username='john_doe', first_name='John', last_name='Doe')
        
        # __str__ returns first_name and last_name
        self.assertIn('John', str(user))
        self.assertIn('Doe', str(user))
    
    def test_username_uniqueness(self):
        """Test that usernames must be unique."""
        User.objects.create_user(username='unique_user', first_name='Test', last_name='User', password='pass123')
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(username='unique_user', first_name='Test', last_name='User', password='pass456')
    
    def test_email_can_be_null(self):
        """Test that email can be null."""
        user = User.objects.create_user(
            username='nomail',
            first_name='No',
            last_name='Mail',
            password='pass123',
            email=None
        )
        
        self.assertIsNone(user.email)
    
    def test_user_role_teacher(self):
        """Test creating user with TEACHER role."""
        teacher = TeacherFactory()
        
        assert_user_has_role(teacher, UserRole.TEACHER)
        self.assertEqual(teacher.role, 0)
    
    def test_user_role_student(self):
        """Test creating user with STUDENT role."""
        student = StudentFactory()
        
        assert_user_has_role(student, UserRole.STUDENT)
        self.assertEqual(student.role, 1)
    
    def test_user_role_admin(self):
        """Test creating user with ADMIN role."""
        admin = AdminFactory()
        
        assert_user_has_role(admin, UserRole.ADMIN)
        self.assertEqual(admin.role, 2)
    
    def test_user_role_parent(self):
        """Test creating user with PARENT role."""
        parent = ParentFactory()
        
        assert_user_has_role(parent, UserRole.PARENT)
        self.assertEqual(parent.role, 3)
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        user = User.objects.create_user(
            username='hashtest',
            first_name='Hash',
            last_name='Test',
            password='plainpassword'
        )
        
        self.assertNotEqual(user.password, 'plainpassword')
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
        self.assertTrue(user.check_password('plainpassword'))
        self.assertFalse(user.check_password('wrongpassword'))
    
    def test_user_phone_field(self):
        """Test user phone field."""
        user = UserFactory(phone='+79001234567')
        
        self.assertEqual(user.phone, '+79001234567')
    
    def test_user_sex_field(self):
        """Test user sex field."""
        male_user = UserFactory(sex=True)
        female_user = UserFactory(sex=False)
        
        self.assertTrue(male_user.sex)
        self.assertFalse(female_user.sex)
    
    def test_user_address_fields(self):
        """Test user address, city, country fields."""
        user = UserFactory(
            address='Ленина 10',
            city='Москва',
            country='Россия'
        )
        
        self.assertEqual(user.address, 'Ленина 10')
        self.assertEqual(user.city, 'Москва')
        self.assertEqual(user.country, 'Россия')
    
    def test_user_clean_method_strips_html(self):
        """Test that clean() method strips HTML tags."""
        user = UserFactory()
        user.address = '<script>alert("XSS")</script>Test Address'
        user.city = '<b>Moscow</b>'
        user.clean()
        
        self.assertNotIn('<script>', user.address)
        self.assertNotIn('<b>', user.city)
        self.assertIn('Test Address', user.address)
        self.assertIn('Moscow', user.city)
    
    def test_update_active_status_method(self):
        """Test update_active_status() method."""
        user = StudentFactory()
        
        # Initially should be active
        self.assertTrue(user.is_active)
        
        # Call update method
        user.update_active_status()
        
        # Should still exist
        self.assertIsNotNone(user.id)


@pytest.mark.unit
class TeacherProfileTest(TestCase):
    """Test cases for TeacherProfile model."""
    
    def test_teacher_profile_creation(self):
        """Test creating teacher profile."""
        teacher = TeacherFactory()
        profile = TeacherProfile.objects.create(user=teacher)
        
        self.assertEqual(profile.user, teacher)
        self.assertIsNotNone(profile.id)
    
    def test_teacher_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with user."""
        teacher = TeacherFactory()
        profile = TeacherProfile.objects.create(user=teacher)
        
        # Should not be able to create another profile for same user
        with self.assertRaises(IntegrityError):
            TeacherProfile.objects.create(user=teacher)
    
    def test_teacher_profile_str_representation(self):
        """Test string representation of teacher profile."""
        teacher = TeacherFactory(username='teacher1')
        profile = TeacherProfile.objects.create(user=teacher)
        
        # TeacherProfile doesn't have custom __str__, so it returns default
        self.assertIsNotNone(str(profile))


@pytest.mark.unit
class StudentProfileTest(TestCase):
    """Test cases for StudentProfile model."""
    
    def test_student_profile_creation(self):
        """Test creating student profile."""
        student = StudentFactory()
        profile = StudentProfile.objects.create(user=student)
        
        self.assertEqual(profile.user, student)
        self.assertIsNotNone(profile.id)
    
    def test_student_profile_source_field(self):
        """Test student profile source field."""
        student = StudentFactory()
        profile = StudentProfile.objects.create(
            user=student,
            source=LeadSource.INTERNET
        )
        
        self.assertEqual(profile.source, LeadSource.INTERNET)
    
    def test_student_profile_source_choices(self):
        """Test all valid source choices."""
        student = StudentFactory()
        
        valid_sources = [
            LeadSource.POSTER,
            LeadSource.RELATIVES,
            LeadSource.FRIENDS,
            LeadSource.VK,
            LeadSource.INTERNET,
            LeadSource.RETURNING,
            LeadSource.OTHER
        ]
        
        for source in valid_sources:
            profile = StudentProfile.objects.create(
                user=StudentFactory(),
                source=source
            )
            self.assertEqual(profile.source, source)
    
    def test_student_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with user."""
        student = StudentFactory()
        profile = StudentProfile.objects.create(user=student)
        
        with self.assertRaises(IntegrityError):
            StudentProfile.objects.create(user=student)


@pytest.mark.unit
class ParentProfileTest(TestCase):
    """Test cases for ParentProfile model."""
    
    def test_parent_profile_creation(self):
        """Test creating parent profile."""
        parent = ParentFactory()
        profile = ParentProfile.objects.create(user=parent)
        
        self.assertEqual(profile.user, parent)
        self.assertIsNotNone(profile.id)
    
    def test_parent_profile_students_relationship(self):
        """Test many-to-many relationship with students."""
        parent = ParentFactory()
        parent_profile = ParentProfile.objects.create(user=parent)
        
        student1 = StudentFactory()
        student2 = StudentFactory()
        student1_profile = StudentProfile.objects.create(user=student1)
        student2_profile = StudentProfile.objects.create(user=student2)
        
        parent_profile.students.add(student1_profile, student2_profile)
        
        self.assertEqual(parent_profile.students.count(), 2)
        self.assertIn(student1_profile, parent_profile.students.all())
        self.assertIn(student2_profile, parent_profile.students.all())
    
    def test_parent_with_multiple_children(self):
        """Test parent with 5 children."""
        parent = ParentFactory()
        parent_profile = ParentProfile.objects.create(user=parent)
        
        for _ in range(5):
            student = StudentFactory()
            student_profile = StudentProfile.objects.create(user=student)
            parent_profile.students.add(student_profile)
        
        self.assertEqual(parent_profile.students.count(), 5)
    
    def test_parent_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with user."""
        parent = ParentFactory()
        profile = ParentProfile.objects.create(user=parent)
        
        with self.assertRaises(IntegrityError):
            ParentProfile.objects.create(user=parent)


@pytest.mark.unit
class UserRoleTest(TestCase):
    """Test cases for UserRole choices."""
    
    def test_user_role_values(self):
        """Test UserRole enum values."""
        self.assertEqual(UserRole.TEACHER, 0)
        self.assertEqual(UserRole.STUDENT, 1)
        self.assertEqual(UserRole.ADMIN, 2)
        self.assertEqual(UserRole.PARENT, 3)
    
    def test_user_role_labels(self):
        """Test UserRole labels."""
        self.assertEqual(UserRole.TEACHER.label, 'Учитель')
        self.assertEqual(UserRole.STUDENT.label, 'Ученик')
        self.assertEqual(UserRole.ADMIN.label, 'Администратор')
        self.assertEqual(UserRole.PARENT.label, 'Родитель')


@pytest.mark.unit
class LeadSourceTest(TestCase):
    """Test cases for LeadSource choices."""
    
    def test_lead_source_values(self):
        """Test LeadSource enum values."""
        self.assertEqual(LeadSource.POSTER, 'poster')
        self.assertEqual(LeadSource.RELATIVES, 'relatives')
        self.assertEqual(LeadSource.FRIENDS, 'friends')
        self.assertEqual(LeadSource.VK, 'vk')
        self.assertEqual(LeadSource.INTERNET, 'internet')
        self.assertEqual(LeadSource.RETURNING, 'returning')
        self.assertEqual(LeadSource.OTHER, 'other')
    
    def test_lead_source_labels(self):
        """Test LeadSource labels."""
        self.assertEqual(LeadSource.POSTER.label, 'Афиша')
        self.assertEqual(LeadSource.RELATIVES.label, 'Рассказали родственники')
        self.assertEqual(LeadSource.FRIENDS.label, 'Рассказали друзья/знакомые')
        self.assertEqual(LeadSource.VK.label, 'ВК')
        self.assertEqual(LeadSource.INTERNET.label, 'Интернет/поиск')
        self.assertEqual(LeadSource.RETURNING.label, 'Уже занимались раньше')
        self.assertEqual(LeadSource.OTHER.label, 'Другое')
