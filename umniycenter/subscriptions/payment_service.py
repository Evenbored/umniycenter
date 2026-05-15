"""
Сервис для работы с платежами через ЮKassa
Обеспечивает безопасное создание и обработку платежей
"""
import uuid
import logging
import hmac
import hashlib
import re
from decimal import Decimal
from datetime import timedelta
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from yookassa import Configuration, Payment as YooPayment

from .models import Payment, Subscription
from accounts.models import CustomUser

logger = logging.getLogger(__name__)

# Инициализация ЮKassa
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

# IP-адреса ЮKassa для проверки webhook (официальные IP)
YOOKASSA_IP_RANGES = [
    '185.71.76.0/27',
    '185.71.77.0/27',
    '77.75.153.0/25',
    '77.75.156.11',
    '77.75.156.35',
    '77.75.154.128/25',
    '2a02:5180::/32',
]


class PaymentService:
    """Сервис для работы с платежами"""

    @staticmethod
    def yookassa_is_configured() -> bool:
        """Проверка, что платежный провайдер реально настроен."""
        shop_id = getattr(settings, 'YOOKASSA_SHOP_ID', None)
        secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', None)

        return bool(
            shop_id and
            secret_key and
            shop_id != 'your_shop_id_here' and
            secret_key != 'your_secret_key_here'
        )

    @staticmethod
    def get_webhook_client_ip(request) -> str:
        """Определить реальный IP webhook без слепого доверия X-Forwarded-For."""
        remote_addr = request.META.get('REMOTE_ADDR')
        trusted_proxies = set(getattr(settings, 'TRUSTED_PROXY_IPS', []))

        if remote_addr in trusted_proxies:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0].strip()

        return remote_addr
    
    @staticmethod
    def validate_webhook_ip(ip_addr: str) -> bool:
        """
        Проверка IP-адреса webhook от ЮKassa
        
        Args:
            ip_addr: IP-адрес отправителя
        
        Returns:
            bool: True если IP разрешен
        """
        try:
            client_ip = ip_address(ip_addr)
            
            for ip_range in YOOKASSA_IP_RANGES:
                if '/' in ip_range:
                    # Это сеть
                    if client_ip in ip_network(ip_range):
                        return True
                else:
                    # Это отдельный IP
                    if client_ip == ip_address(ip_range):
                        return True
            
            logger.warning(f"Webhook from unauthorized IP: {ip_addr}")
            return False
        except ValueError as e:
            logger.error(f"Invalid IP address: {ip_addr}, error: {str(e)}")
            return False
    
    @staticmethod
    def create_payment(subscription_id: int, parent_id: int, payment_method: str = 'online') -> dict:
        """
        Создание платежа для подписки
        
        Args:
            subscription_id: ID подписки
            parent_id: ID родителя (плательщика)
            payment_method: Способ оплаты (online, cash, card, transfer)
        
        Returns:
            dict: Информация о созданном платеже
        
        Raises:
            ValueError: Если данные некорректны
            Exception: При ошибке создания платежа
        """
        allowed_methods = {choice[0] for choice in Payment.PAYMENT_METHOD_CHOICES}
        if payment_method not in allowed_methods:
            raise ValueError("Некорректный способ оплаты")

        try:
            if payment_method == 'online' and not PaymentService.yookassa_is_configured():
                logger.warning("Online payment rejected: YooKassa credentials are not configured")
                raise ValueError("Онлайн-оплата временно недоступна: ЮKassa не настроена")

            # Получаем подписку
            subscription = Subscription.objects.select_related(
                'student', 'tariff', 'tariff__course'
            ).get(id=subscription_id)
            
            # Получаем родителя
            parent = CustomUser.objects.get(id=parent_id)
            
            # Проверяем, что родитель действительно родитель студента
            try:
                student_profile = subscription.student.student_profile
                parent_profile = parent.parent_profile
                
                # Проверяем, что этот родитель связан с этим учеником
                if not student_profile.parents.filter(id=parent_profile.id).exists():
                    logger.warning(
                        f"Payment creation failed: parent {parent_id} is not linked to student {subscription.student.id}"
                    )
                    raise ValueError("Родитель не связан с этим учеником")
            except AttributeError as e:
                logger.error(f"Profile error: {str(e)}")
                raise ValueError("Ошибка проверки связи родитель-ученик")
            
            # Сумма платежа = цена тарифа
            amount = subscription.tariff.price
            
            logger.info(
                f"Creating payment: subscription_id={subscription_id}, parent_id={parent_id}, "
                f"amount={amount}, method={payment_method}"
            )
            
            with transaction.atomic():
                subscription = Subscription.objects.select_for_update().get(id=subscription.id)

                if subscription.status not in ['pending', 'canceled']:
                    raise ValueError("Нельзя создать платеж для уже активной или завершенной подписки")

                if Payment.objects.filter(subscription=subscription, status='completed').exists():
                    raise ValueError("Подписка уже оплачена")

                # Создаем запись платежа в БД только после всех предварительных проверок.
                payment = Payment.objects.create(
                    subscription=subscription,
                    parent=parent,
                    amount=amount,
                    payment_method=payment_method,
                    status='pending'
                )

                logger.info(f"Payment {payment.id} created successfully")

                if subscription.status == 'canceled':
                    subscription.status = 'pending'
                    subscription.save(update_fields=['status', 'updated_at'])

                # Если онлайн-оплата, создаем платеж в ЮKassa.
                if payment_method == 'online':
                    return PaymentService._create_yookassa_payment(payment, subscription)

                logger.info(f"Offline payment {payment.id} awaiting confirmation")
                return {
                    'payment_id': payment.id,
                    'amount': float(amount),
                    'status': 'pending',
                    'payment_method': payment_method,
                    'message': 'Платеж создан. Ожидает подтверждения администратором.'
                }
        
        except Subscription.DoesNotExist:
            logger.error(f"Subscription {subscription_id} not found")
            raise ValueError("Подписка не найдена")
        except CustomUser.DoesNotExist:
            logger.error(f"Parent {parent_id} not found")
            raise ValueError("Родитель не найден")
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def _create_yookassa_payment(payment: Payment, subscription: Subscription) -> dict:
        """
        Создание платежа в ЮKassa
        
        Args:
            payment: Объект платежа из БД
            subscription: Объект подписки
        
        Returns:
            dict: Информация о платеже с URL для оплаты
        """
        try:
            # Формируем описание платежа
            description = settings.PAYMENT_DESCRIPTION_TEMPLATE.format(
                tariff_name=subscription.tariff.name,
                student_name=subscription.student.get_full_name()
            )
            
            # Генерируем уникальный idempotence_key для безопасности
            idempotence_key = str(uuid.uuid4())
            
            logger.info(
                f"Creating YooKassa payment for payment {payment.id}, "
                f"idempotence_key={idempotence_key}"
            )
            
            # Создаем платеж в ЮKassa
            yoo_payment = YooPayment.create({
                "amount": {
                    "value": str(payment.amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": settings.YOOKASSA_RETURN_URL
                },
                "capture": True,  # Автоматическое списание после подтверждения
                "description": description,
                "metadata": {
                    "payment_id": payment.id,
                    "subscription_id": subscription.id,
                    "student_id": subscription.student.id,
                    "parent_id": payment.parent.id
                },
                "receipt": {
                    "customer": {
                        "email": payment.parent.email or "noreply@umny.ru",
                        "phone": payment.parent.phone or ""
                    },
                    "items": [
                        {
                            "description": f"{subscription.tariff.name} ({subscription.tariff.lessons_count} занятий)",
                            "quantity": "1.00",
                            "amount": {
                                "value": str(payment.amount),
                                "currency": "RUB"
                            },
                            "vat_code": 1,  # НДС не облагается
                            "payment_mode": "full_payment",
                            "payment_subject": "service"
                        }
                    ]
                }
            }, idempotence_key)
            
            # Сохраняем данные ЮKassa в нашей БД
            payment.yookassa_payment_id = yoo_payment.id
            payment.yookassa_payment_url = yoo_payment.confirmation.confirmation_url
            payment.save()
            
            logger.info(
                f"YooKassa payment created successfully: yookassa_id={yoo_payment.id}, "
                f"payment_id={payment.id}, confirmation_url={yoo_payment.confirmation.confirmation_url}"
            )
            
            return {
                'payment_id': payment.id,
                'yookassa_payment_id': yoo_payment.id,
                'payment_url': yoo_payment.confirmation.confirmation_url,
                'amount': float(payment.amount),
                'status': yoo_payment.status,
                'message': 'Платеж создан. Перейдите по ссылке для оплаты.'
            }
        
        except Exception as e:
            logger.error(
                f"Error creating YooKassa payment for payment {payment.id}: {str(e)}", 
                exc_info=True
            )
            payment.status = 'failed'
            payment.error_message = str(e)
            payment.save()
            raise Exception(f"Ошибка создания платежа: {str(e)}")
    
    @staticmethod
    def process_webhook(payment_data: dict, client_ip: str = None) -> bool:
        """
        Обработка webhook от ЮKassa
        
        Args:
            payment_data: Данные платежа от ЮKassa
            client_ip: IP-адрес отправителя (для проверки)
        
        Returns:
            bool: True если обработка успешна
        """
        try:
            # Проверяем IP-адрес отправителя (если передан)
            if client_ip and not PaymentService.validate_webhook_ip(client_ip):
                logger.error(f"Webhook rejected: unauthorized IP {client_ip}")
                return False
            
            yookassa_payment_id = payment_data.get('object', {}).get('id')
            status = payment_data.get('object', {}).get('status')
            event_type = payment_data.get('event')
            
            # Получаем сумму из webhook для проверки
            payment_amount_data = payment_data.get('object', {}).get('amount', {})
            webhook_amount = payment_amount_data.get('value')
            
            logger.info(
                f"Processing webhook: event={event_type}, "
                f"yookassa_payment_id={yookassa_payment_id}, status={status}, amount={webhook_amount}"
            )
            
            if not yookassa_payment_id:
                logger.error("No payment ID in webhook data")
                return False
            
            # Используем транзакцию с блокировкой для предотвращения race conditions
            with transaction.atomic():
                # Находим платеж в БД с блокировкой строки (select_for_update)
                try:
                    payment = Payment.objects.select_for_update().select_related(
                        'subscription', 'subscription__student', 'parent'
                    ).get(yookassa_payment_id=yookassa_payment_id)
                    
                    logger.info(f"Found payment {payment.id} for YooKassa payment {yookassa_payment_id}")
                except Payment.DoesNotExist:
                    logger.error(f"Payment with YooKassa ID {yookassa_payment_id} not found in database")
                    return False
                
                # ✅ Idempotency: проверяем, не обработан ли уже этот платеж
                if payment.status == 'completed' and status == 'succeeded':
                    logger.info(f"Payment {payment.id} already processed (idempotency check), skipping")
                    return True
                
                # ✅ Проверка суммы платежа
                if webhook_amount:
                    expected_amount = str(payment.amount)
                    if webhook_amount != expected_amount:
                        logger.error(
                            f"Payment amount mismatch for payment {payment.id}: "
                            f"expected {expected_amount}, got {webhook_amount}"
                        )
                        payment.status = 'failed'
                        payment.error_message = f"Несоответствие суммы: ожидалось {expected_amount}, получено {webhook_amount}"
                        payment.save()
                        return False
                
                # Обрабатываем статус
                if status == 'succeeded':
                    logger.info(f"Payment {payment.id} succeeded, processing...")
                    PaymentService._handle_successful_payment(payment)
                    PaymentService._assign_requested_group(payment)
                elif status == 'canceled':
                    PaymentService.cancel_payment(
                        payment.id,
                        reason='ЮKassa вернула статус canceled',
                        allow_online_provider_cancel=True
                    )
                    logger.info(f"Payment {payment.id} canceled")
                elif status == 'waiting_for_capture':
                    logger.info(f"Payment {payment.id} waiting for capture")
                    # Платеж ожидает подтверждения
                    pass
                else:
                    logger.warning(f"Unknown payment status: {status} for payment {payment.id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    def _handle_successful_payment(payment: Payment):
        """
        Обработка успешного платежа
        
        Args:
            payment: Объект платежа
        """
        try:
            logger.info(f"Handling successful payment {payment.id}")
            
            if payment.payment_method == 'online' and not payment.yookassa_payment_id:
                raise ValueError("Онлайн-платеж без ID ЮKassa не может активировать подписку")

            if payment.amount != payment.subscription.tariff.price:
                raise ValueError("Сумма платежа не соответствует стоимости тарифа")

            # Обновляем статус платежа
            payment.status = 'completed'
            payment.paid_at = timezone.now()
            payment.save()
            
            logger.info(f"Payment {payment.id} marked as completed at {payment.paid_at}")
            
            # Активируем подписку
            subscription = payment.subscription
            if subscription.status == 'active':
                logger.info(f"Subscription {subscription.id} already active")
            else:
                subscription.status = 'active'
                subscription.save()
                logger.info(f"Subscription {subscription.id} activated for student {subscription.student.id}")
            
            # Обновляем статус ученика и родителя
            try:
                subscription.student.update_active_status()
                payment.parent.update_active_status()
                logger.info(f"Updated active status for student {subscription.student.id} and parent {payment.parent.id}")
            except Exception as e:
                logger.warning(f"Could not update active status: {str(e)}")
            
            logger.info(f"Payment {payment.id} processed successfully")
        
        except Exception as e:
            logger.error(f"Error handling successful payment {payment.id}: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def confirm_offline_payment(payment_id: int, confirmed_by: CustomUser = None) -> Payment:
        """Подтвердить офлайн-платеж и активировать подписку."""
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().select_related(
                    'subscription', 'subscription__tariff', 'subscription__student', 'parent'
                ).get(id=payment_id)

                if payment.payment_method == 'online':
                    raise ValueError("Онлайн-платежи подтверждаются только webhook от ЮKassa")
                if payment.status != 'pending':
                    raise ValueError("Подтвердить можно только платеж в статусе ожидания")
                if payment.subscription.status != 'pending':
                    raise ValueError("Подписка должна ожидать оплаты")
                if payment.amount != payment.subscription.tariff.price:
                    raise ValueError("Сумма платежа не соответствует стоимости тарифа")

                note = "Оплата подтверждена администратором"
                if confirmed_by:
                    note += f" #{confirmed_by.id}"
                payment.notes = f"{payment.notes}\n{note}".strip()

                PaymentService._handle_successful_payment(payment)
                PaymentService._assign_requested_group(payment)
                payment.refresh_from_db()
                return payment
        except Payment.DoesNotExist:
            raise ValueError("Платеж не найден")

    @staticmethod
    def _assign_requested_group(payment: Payment):
        """Добавить ученика в группу, выбранную при покупке, только после оплаты."""
        match = re.search(r'requested_group_id=(\d+)', payment.notes or '')
        if not match:
            return

        try:
            from groups.models import SchoolGroups
            from students.models import StudentGroups

            group = SchoolGroups.objects.get(id=int(match.group(1)))
            subscription = payment.subscription
            if group.course_id != subscription.tariff.course_id:
                logger.warning(
                    f"Requested group {group.id} course does not match subscription {subscription.id} course"
                )
                return

            StudentGroups.objects.get_or_create(student=subscription.student, group=group)
        except Exception as e:
            logger.warning(f"Could not assign requested group after payment {payment.id}: {str(e)}")

    @staticmethod
    def cancel_payment(
        payment_id: int,
        canceled_by: CustomUser = None,
        reason: str = '',
        allow_online_provider_cancel: bool = False
    ) -> Payment:
        """Отменить неоплаченный платеж и закрыть ожидающую подписку."""
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().select_related(
                    'subscription', 'subscription__student', 'parent'
                ).get(id=payment_id)

                if payment.status == 'completed':
                    raise ValueError("Оплаченный платеж нельзя отменить этим действием")
                if payment.payment_method == 'online' and payment.status == 'pending' and not allow_online_provider_cancel:
                    raise ValueError("Ожидающий онлайн-платеж закрывается только статусом от ЮKassa")
                if payment.status in ['canceled', 'failed']:
                    return payment

                payment.status = 'canceled'
                note = "Платеж отменен администратором"
                if canceled_by:
                    note += f" #{canceled_by.id}"
                if reason:
                    note += f": {reason}"
                payment.notes = f"{payment.notes}\n{note}".strip()
                payment.save(update_fields=['status', 'notes', 'updated_at'])

                subscription = payment.subscription
                if subscription.status == 'pending' and not subscription.payments.filter(status='completed').exists():
                    subscription.status = 'canceled'
                    subscription.save(update_fields=['status', 'updated_at'])
                    subscription.student.update_active_status()
                    payment.parent.update_active_status()

                return payment
        except Payment.DoesNotExist:
            raise ValueError("Платеж не найден")
    
    @staticmethod
    def get_payment_status(payment_id: int) -> dict:
        """
        Получение статуса платежа
        
        Args:
            payment_id: ID платежа в нашей БД
        
        Returns:
            dict: Информация о статусе платежа
        """
        try:
            payment = Payment.objects.select_related('subscription', 'parent').get(id=payment_id)
            
            result = {
                'payment_id': payment.id,
                'amount': float(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'created_at': payment.created_at.isoformat(),
                'paid_at': payment.paid_at.isoformat() if payment.paid_at else None
            }
            
            # Если онлайн-оплата, проверяем статус в ЮKassa
            if payment.payment_method == 'online' and payment.yookassa_payment_id:
                try:
                    yoo_payment = YooPayment.find_one(payment.yookassa_payment_id)
                    result['yookassa_status'] = yoo_payment.status
                    result['payment_url'] = payment.yookassa_payment_url
                except Exception as e:
                    logger.error(f"Error fetching YooKassa status: {str(e)}")
            
            return result
        
        except Payment.DoesNotExist:
            raise ValueError("Платеж не найден")
