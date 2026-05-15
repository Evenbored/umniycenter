from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model, authenticate
from django.utils.html import strip_tags
from django.core.validators import RegexValidator
from courses.models import Courses
from accounts.models import LeadSource
from .models import *


class ParticipantRequestForm(forms.ModelForm):
    parent_fio = forms.CharField(
        required=True,
        max_length=150,
        label="ФИО родителя",
        widget=forms.TextInput(attrs={
            'class': 'form-control border-0',
            'id': 'gname',
            'placeholder': 'Иванов Иван Иванович'
        })
    )
    child_fio = forms.CharField(
        required=True,
        max_length=150,
        label="ФИО ребенка",
        widget=forms.TextInput(attrs={
            'class': 'form-control border-0',
            'id': 'cname',
            'placeholder': 'Иванов Петр Иванович'
        })
    )
    phone = forms.CharField(
        required=True,
        max_length=20,
        label="Телефон",
        validators=[
            RegexValidator(
                regex=r'^\+7\d{10}$',
                message='Номер должен начинаться с +7 и содержать 10 цифр (например: +79001234567)'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control border-0',
            'id': 'phone',
            'placeholder': '+79001234567',
            'pattern': r'\+7\d{10}',
            'title': 'Формат: +7XXXXXXXXXX (10 цифр после +7)'
        })
    )
    age = forms.CharField(
        required=True,
        max_length=3,
        label="Возраст ребенка",
        widget=forms.NumberInput(attrs={
            'class': 'form-control border-0',
            'id': 'cage',
            'placeholder': '7',
            'min': '1',
            'max': '18'
        })
    )
    source = forms.ChoiceField(
        choices=[('', 'Выберите источник')] + list(LeadSource.choices),
        required=False,
        label="Как вы узнали о центре?",
        widget=forms.Select(attrs={
            'class': 'form-select border-0',
            'id': 'source'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Безопасная загрузка курсов
        try:
            self.fields['courses'] = forms.ModelMultipleChoiceField(
                queryset=Courses.objects.all(),
                required=True,
                label="Выберите курсы",
                widget=forms.CheckboxSelectMultiple(attrs={
                    'class': 'form-check-input'
                })
            )
        except Exception:
            # Если БД недоступна, создаем пустое поле
            self.fields['courses'] = forms.ModelMultipleChoiceField(
                queryset=Courses.objects.none(),
                required=False,
                label="Выберите курсы",
                widget=forms.CheckboxSelectMultiple(attrs={
                    'class': 'form-check-input'
                })
            )
    
    class Meta:
        model = ParticipantRequest
        fields = ['parent_fio', 'child_fio', 'phone', 'age', 'courses', 'source']
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not phone.startswith('+7'):
            raise forms.ValidationError('Номер телефона должен начинаться с +7')
        if phone and len(phone) != 12:
            raise forms.ValidationError('Номер телефона должен содержать ровно 12 символов (+7 и 10 цифр)')
        return phone
    
    def clean_parent_fio(self):
        """Очистка ФИО родителя от HTML-тегов для защиты от XSS"""
        parent_fio = self.cleaned_data.get('parent_fio', '')
        return strip_tags(parent_fio).strip()
    
    def clean_child_fio(self):
        """Очистка ФИО ребенка от HTML-тегов для защиты от XSS"""
        child_fio = self.cleaned_data.get('child_fio', '')
        return strip_tags(child_fio).strip()
    
    def clean_age(self):
        """Очистка возраста от HTML-тегов"""
        age = self.cleaned_data.get('age', '')
        return strip_tags(str(age)).strip()
