from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.html import strip_tags
from django.contrib.auth.hashers import make_password

class UserRole(models.IntegerChoices):
        TEACHER = 0, 'Учитель'
        STUDENT = 1, 'Ученик'
        ADMIN = 2, 'Администратор'
        PARENT = 3, 'Родитель'

class UserSex(models.IntegerChoices):
        MAN = 0, 'Мужской'
        WOMEN = 1, 'Женский'

class LeadSource(models.TextChoices):
        POSTER = 'poster', 'Афиша'
        RELATIVES = 'relatives', 'Рассказали родственники'
        FRIENDS = 'friends', 'Рассказали друзья/знакомые'
        VK = 'vk', 'ВК'
        INTERNET = 'internet', 'Интернет/поиск'
        RETURNING = 'returning', 'Уже занимались раньше'
        OTHER = 'other', 'Другое'

class CustomUserManager(BaseUserManager):
    def create_user(self, username, first_name, last_name, email=None, phone=None, role=None, password=None, **extra_fields):
        if not username:
            raise ValueError('Логин пользователя не указан')
        if email:
            email = self.normalize_email(email)
        user = self.model(
            email=email, 
            first_name=first_name, 
            last_name=last_name, 
            phone=phone, 
            role=role if role is not None else UserRole.STUDENT, 
            username=username, 
            **extra_fields
        )
        
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, first_name, last_name, email=None, phone=None, role=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь соответствующие права')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь соответствующие права')
        
        # Для superuser по умолчанию роль ADMIN
        if role is None:
            role = UserRole.ADMIN
        
        return self.create_user(username, first_name, last_name, email, phone, role, password, **extra_fields)

class CustomUser(AbstractUser):
    
    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)
    
    def update_active_status(self):
        """Обновить статус активности пользователя на основе подписок"""
        from django.db.models import F, Q
        from django.utils import timezone
        
        if self.role == UserRole.STUDENT:
            # Ученик активен, если есть активные подписки с занятиями
            has_active_subscription = self.subscriptions.filter(
                status='active',
                lessons_used__lt=F('lessons_total'),
                end_date__gte=timezone.now().date()
            ).exists()
            
            self.is_active = has_active_subscription
            self.save(update_fields=['is_active'])
        
        elif self.role == UserRole.PARENT:
            # Родитель активен, если хотя бы один его ребенок активен
            try:
                has_active_children = self.parent_profile.students.filter(
                    user__is_active=True
                ).exists()
                
                self.is_active = has_active_children
                self.save(update_fields=['is_active'])
            except Exception:
                pass
    email = models.EmailField(unique=True, max_length=254, verbose_name="Почта", blank=True, null=True)
    first_name = models.CharField(max_length=66, verbose_name="Имя")
    last_name = models.CharField(max_length=66, verbose_name="Фамилия")
    address =  models.CharField(max_length=128, blank=True, null=True, verbose_name="Адрес")
    city =  models.CharField(max_length=60, blank=True, null=True, verbose_name="Город")
    country =  models.CharField(max_length=60, blank=True, null=True, verbose_name="Страна")
    phone =  models.CharField(max_length=15, blank=True, null=True, verbose_name="Номер телефона")
    sex = models.BooleanField(choices=tuple(map(lambda x: (bool(x[0]), x[1]), UserSex.choices)),
                                       default=UserSex.MAN, verbose_name="Пол")
    username = models.CharField(max_length=150, unique=True, verbose_name="Имя пользователя")
    role = models.PositiveSmallIntegerField(choices=UserRole.choices,default=UserRole.STUDENT,
                                            verbose_name="Роль")
    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
            verbose_name = ("Пользователя")
            verbose_name_plural = ("Пользователи")
    
    def __str__(self):
        return f'{self.first_name} {self.last_name}'
    
    def clean(self):
        for field in ['first_name', 'last_name', 'address', 'city', 'country', 'sex', 'phone']:
            value = getattr(self, field)
            if value:
                setattr(self, field, strip_tags(value))

class TeacherProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="teacher_profile"
    )

class StudentProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="student_profile"
    )
    source = models.CharField(
        max_length=20,
        choices=LeadSource.choices,
        blank=True,
        null=True,
        verbose_name="Источник привлечения"
    )

class ParentProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="parent_profile"
    )

    students = models.ManyToManyField(
        StudentProfile,
        related_name="parents",
        blank=True
    )
