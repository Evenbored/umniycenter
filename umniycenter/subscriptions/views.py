from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import logging

from .models import Payment

logger = logging.getLogger(__name__)


@login_required
def payment_success(request):
    """
    Страница успешной оплаты
    Пользователь попадает сюда после оплаты через ЮKassa
    """
    # Получаем параметры из URL (ЮKassa передает их)
    payment_id = request.GET.get('payment_id')
    
    context = {
        'payment_id': payment_id,
    }
    
    # Если есть ID платежа, пытаемся получить информацию
    if payment_id:
        try:
            payment = Payment.objects.select_related(
                'subscription', 
                'subscription__student',
                'subscription__tariff'
            ).get(yookassa_payment_id=payment_id)
            
            context['payment'] = payment
            context['subscription'] = payment.subscription
            context['student'] = payment.subscription.student
            
            logger.info(f"Payment success page viewed: payment_id={payment.id}, user={request.user.id}")
            
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for yookassa_payment_id={payment_id}")
            messages.warning(request, 'Платеж не найден в системе.')
    
    return render(request, 'subscriptions/payment_success.html', context)


@login_required
def payment_failed(request):
    """
    Страница неудачной оплаты
    """
    payment_id = request.GET.get('payment_id')
    
    logger.info(f"Payment failed page viewed: payment_id={payment_id}, user={request.user.id}")
    
    context = {
        'payment_id': payment_id,
    }
    
    return render(request, 'subscriptions/payment_failed.html', context)
