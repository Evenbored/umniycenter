from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model, authenticate
from django.utils.html import strip_tags
from django.core.validators import RegexValidator
from .models import *

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=True, max_length=50, widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Имя'}))
    last_name = forms.CharField(required=True, max_length=50, widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Фамилия'}))
    username =  forms.CharField(required=True, max_length=50, widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Имя пользователя'}))
    phone = forms.CharField(required=True, validators=[RegexValidator(r'^\+?1?\d{9,15}$', "Enter a valid phone number.")],widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Номер телефона'}))
    email = forms.EmailField(required=True, max_length=66, widget=forms.EmailInput(attrs={'class': 'input-register form-control', 'placeholder': 'Почта'}))
    password1 = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'class': 'input-register form-control', 'placeholder': 'Пароль'}))
    password2 = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'class': 'input-register form-control', 'placeholder': 'Пароль'}))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'phone', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Такая почта уже существует')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким именем уже существует')
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        return user
    
class CustomUserLoginForm(AuthenticationForm):
    username = forms.CharField(label='Имя пользователя', 
                               widget=forms.TextInput(attrs={'autofocus': True, 'class': '', 'placeholder': 'Имя пользователя'}))
    password = forms.CharField(label='Пароль', 
                               widget=forms.PasswordInput(attrs={'autofocus': True, 'class': '', 'placeholder': 'Пароль'}))
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Такого пользователя не существует")
            elif not self.user_cache.is_active:
                raise forms.ValidationError('Данный аккаунт был отключен')
            return self.cleaned_data

class CustomUserUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        required=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', "Enter a valid phone number.")],
        widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Номер телефона'})
    )
    first_name = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Имя'})
    )
    last_name = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Фамилия'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'input-register form-control', 'placeholder': 'Почта'})
    )
    username =  forms.CharField(
        required=True, 
        max_length=50, 
        widget=forms.TextInput(attrs={'class': 'input-register form-control', 'placeholder': 'Имя пользователя'}))

    

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'address', 
                  'city', 'country', 'phone', 'sex')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'input-register form-control', 
                                             'placeholder': 'Почта'}),
            'first_name': forms.TextInput(attrs={'class': 'input-register form-control', 
                                                 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'input-register form-control', 
                                                'placeholder': 'Фамилия'}),
            'address': forms.TextInput(attrs={'class': 'input-register form-control', 
                                               'placeholder': 'Адрес'}),
            'city': forms.TextInput(attrs={'class': 'input-register form-control', 
                                           'placeholder': 'Город'}),
            'country': forms.TextInput(attrs={'class': 'input-register form-control', 
                                              'placeholder': 'Страна'}),
            'phone': forms.TextInput(attrs={'class': 'input-register form-control', 
                                               'placeholder': 'Номер телфона'}),
            'sex': forms.TextInput(attrs={'class': 'input-register form-control', 
                                                  'placeholder': 'Пол'}),
        }

    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError('Такая почта уже занята')
        return email
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(email=username).exclude(id=self.instance.id).exists():
            raise forms.ValidationError('Такое имя пользователя уже занято')
        return username

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('username'):
            cleaned_data['username'] = self.instance.username

        for field in ['first_name', 'last_name', 'address', 'city', 'country', 'sex', 'phone']:
            if cleaned_data.get(field):
                cleaned_data[field] = strip_tags(cleaned_data[field])

        return cleaned_data
