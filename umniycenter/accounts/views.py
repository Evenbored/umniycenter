from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from schedule.services import get_user_schedule
from .forms import *
from django.contrib.auth.decorators import user_passes_test

def staff_required(login_url=None):
    return user_passes_test(lambda u: u.is_staff, login_url=login_url)

def teacher_required(view_func):
    def _wrapped(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect("../login")
        
        if request.user.role != UserRole.TEACHER:
            return HttpResponseForbidden()
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped
  
def logout_view(request):
    logout(request)
    return redirect('accounts:login')

def register(requst):
    if requst.method == "POST":
        form = CustomUserCreationForm(requst.POST)
        if form.is_valid():
            user = form.save()
            login(requst, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('accounts:profile')
    else:
        form = CustomUserCreationForm()
    return render(requst, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomUserLoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if user.role == UserRole.ADMIN:
                return redirect('/crm/')
            return redirect('accounts:profile')
    else:
        if (CustomUser.objects.filter(id=request.user.id).exists()):
            if request.user.role == UserRole.ADMIN:
                return redirect('/crm/')
            return redirect('accounts:profile')
        form = CustomUserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def profile_view(request):
    if request.user.role == UserRole.ADMIN:
        return redirect('/crm/')
    schedule = get_user_schedule(request.user)
    return render(request, 'accounts/profile.html', {'user': request.user, 'schedule': schedule})

@login_required
def account_details(request):
    user = CustomUser.objects.get(id=request.user.id)
    return render(request, 'accounts/partials/account_details.html',
                  {'user': user})

@login_required
def edit_self_account_details(request):
    form = CustomUserUpdateForm(request.POST, instance=request.user)
    return render(request, 'accounts/edit_account_details.html')

@login_required
def edit_account_details(request):
    form = CustomUserUpdateForm(instance=request.user)
    return render(request, 'accounts/partials/edit_account_details.html', 
                  {'user': request.user, 'form': form})

@login_required
def update_account_details(request):
    if request.method == 'POST':
        form = CustomUserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.clean()  
            user.save()
            return render(request, 'accounts/partials/account_details.html', {'user': user})
        else:
            return render(request, 'accounts/partials/edit_account_details.html', {'user': request.user, 'form': form})
    return render(request, 'accounts/partials/account_details.html', {'user': request.user})

@login_required
def messages_view(request):
    # Только родители могут получить доступ к странице сообщений
    if request.user.role != 3:  # 3 = PARENT
        return redirect('accounts:profile')
    return render(request, 'accounts/messages.html', {'user': request.user})
