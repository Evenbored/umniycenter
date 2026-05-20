from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import *


def main_page(request):
    if request.method == "POST":
        form = ParticipantRequestForm(request.POST)
        if form.is_valid():
            particRequest = form.save()
            try:
                from sales.models import Lead
                from tasks.services import TaskService
                lead = Lead.from_participant_request(particRequest)
                TaskService.create_for_lead(lead)
            except Exception:
                pass
            messages.success(
                request,
                f'Спасибо за заявку! Мы свяжемся с вами по номеру {particRequest.phone} в ближайшее время.'
            )
            return redirect('main:main_page')
        else:
            messages.error(
                request,
                'Пожалуйста, исправьте ошибки в форме и попробуйте снова.'
            )
    else:
        form = ParticipantRequestForm()
    
    return render(request, 'main/index/index.html', {'form': form})
