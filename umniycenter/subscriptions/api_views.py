from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomUser, UserRole
from accounts.permissions import IsAdminRole, IsAdminOrTeacherRole
from .models import Tariff, Subscription, Payment, LessonAttendance
from .serializers import (
    TariffSerializer,
    SubscriptionSerializer,
    PaymentSerializer,
    LessonAttendanceSerializer,
    CreateSubscriptionSerializer
)
from .payment_service import PaymentService

logger = logging.getLogger(__name__)


class TariffListAPIView(ListAPIView):
    """Список доступных тарифов"""
    serializer_class = TariffSerializer
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        queryset = Tariff.objects.select_related('course')

        active = self.request.query_params.get('active')
        if active is not None:
            queryset = queryset.filter(is_active=active.lower() == 'true')
        
        # Фильтр по курсу
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        # Фильтр по типу (пробные/платные)
        is_trial = self.request.query_params.get('is_trial')
        if is_trial is not None:
            queryset = queryset.filter(is_trial=is_trial.lower() == 'true')

        subscription_type = self.request.query_params.get('subscription_type')
        if subscription_type:
            queryset = queryset.filter(subscription_type=subscription_type)
        
        return queryset.order_by('course', 'lessons_count')


class TariffDetailAPIView(RetrieveUpdateDestroyAPIView):
    """Просмотр, обновление и удаление тарифа"""
    queryset = Tariff.objects.select_related('course')
    serializer_class = TariffSerializer
    permission_classes = [IsAdminRole]


@api_view(['POST'])
def create_tariff(request):
    """Создать тариф"""
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать тарифы"}, status=status.HTTP_403_FORBIDDEN)

    serializer = TariffSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    tariff = serializer.save()

    return Response({
        "message": "Тариф создан",
        "tariff": TariffSerializer(tariff).data,
    }, status=status.HTTP_201_CREATED)


class StudentSubscriptionsAPIView(ListAPIView):
    """Список подписок ученика"""
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        student_id = self.kwargs.get('student_id')
        
        queryset = Subscription.objects.filter(
            student_id=student_id
        ).select_related('student', 'parent', 'tariff', 'tariff__course')
        
        # Фильтр по статусу
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')


class PaymentsListAPIView(ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'parent',
            'subscription',
            'subscription__student',
            'subscription__tariff',
            'subscription__tariff__course',
        )

        status_filter = self.request.query_params.get('status')
        method_filter = self.request.query_params.get('method')
        search = self.request.query_params.get('search')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if method_filter:
            queryset = queryset.filter(payment_method=method_filter)

        if search:
            queryset = queryset.filter(
                Q(parent__first_name__icontains=search) |
                Q(parent__last_name__icontains=search) |
                Q(parent__phone__icontains=search) |
                Q(parent__email__icontains=search) |
                Q(subscription__student__first_name__icontains=search) |
                Q(subscription__student__last_name__icontains=search) |
                Q(subscription__tariff__name__icontains=search) |
                Q(subscription__tariff__course__name__icontains=search) |
                Q(transaction_id__icontains=search) |
                Q(yookassa_payment_id__icontains=search)
            )

        return queryset.order_by('-created_at')


@api_view(['POST'])
def create_subscription(request):
    """Создать подписку с платежом"""
    if request.user.role != UserRole.ADMIN:
        return Response(
            {"error": "Только администратор может создавать подписки"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = CreateSubscriptionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data

    if data['payment_method'] == 'online':
        return Response(
            {"error": "Онлайн-подписки создаются только через защищенный платежный поток"},
            status=status.HTTP_400_BAD_REQUEST
        )
    if data['payment_status'] == 'completed' and data['payment_method'] not in ['cash', 'card', 'transfer']:
        return Response(
            {"error": "Автоматическое подтверждение разрешено только для офлайн-оплат"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        student = CustomUser.objects.get(id=data['student_id'])
        parent = CustomUser.objects.get(id=data['parent_id'])
        tariff = Tariff.objects.get(id=data['tariff_id'])
    except CustomUser.DoesNotExist:
        return Response({"error": "Пользователь не найден"}, status=status.HTTP_404_NOT_FOUND)
    except Tariff.DoesNotExist:
        return Response({"error": "Тариф не найден"}, status=status.HTTP_404_NOT_FOUND)
    
    with transaction.atomic():
        # Создаем подписку со статусом pending
        # Активируется только после подтверждения оплаты
        subscription = Subscription.objects.create(
            student=student,
            parent=parent,
            tariff=tariff,
            lessons_total=tariff.lessons_count,
            lessons_used=0,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=tariff.validity_days),
            status='pending'  # ❗ Подписка неактивна до оплаты
        )
        
        # Создаем платеж
        payment = Payment.objects.create(
            subscription=subscription,
            parent=parent,
            amount=tariff.price,
            payment_method=data['payment_method'],
            status=data['payment_status'],
            notes=data.get('notes', ''),
            paid_at=timezone.now() if data['payment_status'] == 'completed' else None
        )
        
        # ✅ Активируем подписку только если платеж уже completed
        # Для офлайн платежей (cash, card, transfer) со статусом 'completed'
        if payment.status == 'completed' and payment.payment_method in ['cash', 'card', 'transfer']:
            subscription.status = 'active'
            subscription.save()
            
            # Обновляем статус ученика и родителя
            student.update_active_status()
            parent.update_active_status()
    
    return Response({
        "message": "Подписка успешно создана",
        "subscription": SubscriptionSerializer(subscription).data,
        "payment": PaymentSerializer(payment).data
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def quick_create_subscription(request):
    """Создать покупку тарифа и платеж одним атомарным действием."""
    if request.user.role != UserRole.ADMIN:
        return Response(
            {"error": "Только администратор может создавать подписки"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    student_id = request.data.get('student_id')
    tariff_id = request.data.get('tariff_id')
    group_id = request.data.get('group_id')  # Опциональное поле
    payment_method = request.data.get('payment_method', 'cash')
    
    if not student_id or not tariff_id:
        return Response(
            {"error": "Необходимо указать student_id и tariff_id"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        student = CustomUser.objects.get(id=student_id, role=UserRole.STUDENT)
        tariff = Tariff.objects.get(id=tariff_id)
        
        # Находим родителя ученика
        try:
            student_profile = student.student_profile
            parent_profile = student_profile.parents.first()
            
            if not parent_profile:
                logger.error(f"Student {student_id} has no parent linked. Student profile exists: {student_profile.id}")
                return Response(
                    {"error": "У ученика нет привязанного родителя. Добавьте родителя в карточке ученика."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            parent = parent_profile.user
            logger.info(f"Found parent {parent.id} for student {student_id}")
        except AttributeError as e:
            logger.error(f"Student {student_id} has no student_profile: {str(e)}")
            return Response(
                {"error": "У ученика отсутствует профиль. Обратитесь к администратору."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error finding parent for student {student_id}: {str(e)}")
            return Response(
                {"error": f"Ошибка при поиске родителя: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except CustomUser.DoesNotExist:
        return Response({"error": "Ученик не найден"}, status=status.HTTP_404_NOT_FOUND)
    except Tariff.DoesNotExist:
        return Response({"error": "Тариф не найден"}, status=status.HTTP_404_NOT_FOUND)
    
    group = None
    if group_id:
        try:
            from groups.models import SchoolGroups

            group = SchoolGroups.objects.get(id=group_id)
            if group.course_id != tariff.course_id:
                return Response(
                    {"error": "Курс группы не соответствует курсу тарифа"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except SchoolGroups.DoesNotExist:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

    if tariff.subscription_type == Tariff.SUBSCRIPTION_TYPE_GROUP and not group:
        return Response(
            {"error": "Для группового абонемента нужно выбрать группу"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if tariff.subscription_type == Tariff.SUBSCRIPTION_TYPE_INDIVIDUAL and group:
        return Response(
            {"error": "Индивидуальный абонемент не привязывается к группе"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            subscription = Subscription.objects.create(
                student=student,
                parent=parent,
                tariff=tariff,
                lessons_total=tariff.lessons_count,
                lessons_used=0,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timedelta(days=tariff.validity_days),
                status='pending'
            )

            payment_result = PaymentService.create_payment(
                subscription_id=subscription.id,
                parent_id=parent.id,
                payment_method=payment_method
            )

            payment = Payment.objects.get(id=payment_result['payment_id'])

            if group:
                payment.notes = f"{payment.notes}\nrequested_group_id={group.id}".strip()
                payment.save(update_fields=['notes', 'updated_at'])

            # Группа не дает доступа до оплаты. Добавляем только после фактической активации.
            group_added = False
            subscription.refresh_from_db(fields=['status'])
            if group and subscription.status == 'active':
                from students.models import StudentGroups

                if not StudentGroups.objects.filter(student=student, group=group).exists():
                    StudentGroups.objects.create(student=student, group=group)
                    group_added = True
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error creating subscription purchase: {str(e)}", exc_info=True)
        return Response({"error": "Ошибка создания платежа"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    response_data = {
        "message": "Подписка создана. Ожидает оплаты.",
        "subscription": SubscriptionSerializer(subscription).data,
        "payment": PaymentSerializer(payment).data,
        "payment_result": payment_result
    }

    if payment_result.get('payment_url'):
        response_data['payment_url'] = payment_result['payment_url']
    
    if group_added:
        response_data["message"] += " и ученик добавлен в группу"
        response_data["group_added"] = True
    
    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def mark_attendance(request):
    """Отметить посещение занятия"""
    if request.user.role not in [UserRole.ADMIN, UserRole.TEACHER]:
        return Response(
            {"error": "Только администратор или учитель могут отмечать посещаемость"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    schedule_id = request.data.get('schedule_id')
    student_id = request.data.get('student_id')
    attendance_status = request.data.get('status')  # present, absent, excused
    lessons_count = request.data.get('lessons_count', 2)  # 1 или 2 занятия
    notes = request.data.get('notes', '')
    
    if not all([schedule_id, student_id, attendance_status]):
        return Response(
            {"error": "Необходимо указать schedule_id, student_id и status"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from schedule.models import Schedule
        schedule = Schedule.objects.get(id=schedule_id)
        student = CustomUser.objects.get(id=student_id, role=UserRole.STUDENT)
    except Schedule.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)
    except CustomUser.DoesNotExist:
        return Response({"error": "Ученик не найден"}, status=status.HTTP_404_NOT_FOUND)

    if schedule.student_id and schedule.student_id != student.id:
        return Response(
            {"error": "Этот ученик не записан на выбранное индивидуальное/разовое занятие"},
            status=status.HTTP_400_BAD_REQUEST
        )

    active_subscription = None
    
    # Проверяем, нет ли уже отметки
    existing = LessonAttendance.objects.filter(
        schedule=schedule,
        student=student
    ).first()
    
    if existing:
        return Response(
            {"error": "Посещение уже отмечено для этого ученика"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Если ученик присутствовал, проверяем наличие достаточного количества занятий ДО создания записи
    if attendance_status == 'present' and not schedule.is_single:
        # Ищем активную подписку для этого курса
        subscription_type = (
            Tariff.SUBSCRIPTION_TYPE_GROUP
            if schedule.group_id
            else Tariff.SUBSCRIPTION_TYPE_INDIVIDUAL
        )
        active_subscription = Subscription.objects.filter(
            student=student,
            status='active',
            tariff__course=schedule.group.course if schedule.group else schedule.course,
            tariff__subscription_type=subscription_type,
            end_date__gte=timezone.now().date()
        ).order_by('end_date').first()
        
        if not active_subscription:
            return Response(
                {"error": "У ученика нет активной подписки на этот курс"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if active_subscription.lessons_remaining < lessons_count:
            return Response(
                {"error": f"Недостаточно занятий. Осталось: {active_subscription.lessons_remaining}, требуется: {lessons_count}"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    with transaction.atomic():
        # Создаем отметку посещения
        attendance = LessonAttendance.objects.create(
            schedule=schedule,
            student=student,
            status=attendance_status,
            lessons_count=lessons_count,
            notes=notes,
            marked_by=request.user
        )
        
        # Если ученик присутствовал, списываем занятия
        if attendance_status == 'present' and not schedule.is_single:
            # Списываем занятия (подписка уже проверена выше)
            active_subscription.deduct_lessons(lessons_count)
            
            attendance.subscription = active_subscription
            attendance.lesson_deducted = True
            attendance.save()
            
            # Обновляем статус ученика
            student.update_active_status()
    
    return Response({
        "message": "Посещение успешно отмечено",
        "attendance": LessonAttendanceSerializer(attendance).data
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def cancel_attendance(request, attendance_id):
    """Отменить отметку посещения и вернуть занятия"""
    if request.user.role != UserRole.ADMIN:
        return Response(
            {"error": "Только администратор может отменять посещаемость"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        attendance = LessonAttendance.objects.get(id=attendance_id)
    except LessonAttendance.DoesNotExist:
        return Response({"error": "Отметка не найдена"}, status=status.HTTP_404_NOT_FOUND)
    
    with transaction.atomic():
        # Если занятия были списаны, возвращаем их
        if attendance.lesson_deducted and attendance.subscription:
            attendance.subscription.refund_lessons(attendance.lessons_count)
            
            # Обновляем статус ученика
            attendance.student.update_active_status()
        
        # Удаляем отметку
        attendance.delete()
    
    return Response({
        "message": "Отметка посещения отменена, занятия возвращены"
    }, status=status.HTTP_200_OK)


class StudentAttendanceHistoryAPIView(ListAPIView):
    """История посещений ученика"""
    serializer_class = LessonAttendanceSerializer
    permission_classes = [IsAdminOrTeacherRole]
    
    def get_queryset(self):
        student_id = self.kwargs.get('student_id')
        
        queryset = LessonAttendance.objects.filter(
            student_id=student_id
        ).select_related('schedule', 'student', 'subscription', 'marked_by')
        
        return queryset.order_by('-created_at')


# ============================================
# ПЛАТЕЖИ (PAYMENTS)
# ============================================

@api_view(['POST'])
def create_payment(request):
    """
    Создание платежа для подписки
    
    Body:
    {
        "subscription_id": 1,
        "parent_id": 2,
        "payment_method": "online"  // online, cash, card, transfer
    }
    """
    if request.user.role != UserRole.ADMIN:
        return Response(
            {"error": "Только администратор может создавать платежи"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    subscription_id = request.data.get('subscription_id')
    parent_id = request.data.get('parent_id')
    payment_method = request.data.get('payment_method', 'online')
    
    if not subscription_id or not parent_id:
        return Response(
            {"error": "Укажите subscription_id и parent_id"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        result = PaymentService.create_payment(
            subscription_id=subscription_id,
            parent_id=parent_id,
            payment_method=payment_method
        )
        return Response(result, status=status.HTTP_201_CREATED)
    
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        return Response(
            {"error": "Ошибка создания платежа"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_payment_status(request, payment_id):
    """Получение статуса платежа"""
    try:
        result = PaymentService.get_payment_status(payment_id)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return Response(
            {"error": "Ошибка получения статуса платежа"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def confirm_payment(request, payment_id):
    """Подтвердить офлайн-оплату администратором."""
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может подтверждать платежи"}, status=status.HTTP_403_FORBIDDEN)

    try:
        payment = PaymentService.confirm_offline_payment(payment_id, confirmed_by=request.user)
        return Response({
            "message": "Оплата подтверждена, подписка активирована",
            "payment": PaymentSerializer(payment).data,
            "subscription": SubscriptionSerializer(payment.subscription).data,
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error confirming payment {payment_id}: {str(e)}", exc_info=True)
        return Response({"error": "Ошибка подтверждения платежа"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_payment(request, payment_id):
    """Отменить неоплаченный платеж и pending-подписку."""
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может отменять платежи"}, status=status.HTTP_403_FORBIDDEN)

    reason = request.data.get('reason', '') if isinstance(request.data, dict) else ''

    try:
        payment = PaymentService.cancel_payment(payment_id, canceled_by=request.user, reason=reason)
        return Response({
            "message": "Платеж отменен, неоплаченная подписка закрыта",
            "payment": PaymentSerializer(payment).data,
            "subscription": SubscriptionSerializer(payment.subscription).data,
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error canceling payment {payment_id}: {str(e)}", exc_info=True)
        return Response({"error": "Ошибка отмены платежа"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
def yookassa_webhook(request):
    """
    Webhook для обработки уведомлений от ЮKassa
    Вызывается автоматически при изменении статуса платежа
    """
    try:
        # Получаем IP отправителя. X-Forwarded-For учитывается только от доверенного прокси.
        client_ip = PaymentService.get_webhook_client_ip(request)
        
        logger.info(f"Received webhook from IP: {client_ip}")
        
        # Получаем данные от ЮKassa
        payment_data = json.loads(request.body)
        
        logger.info(f"Received YooKassa webhook: event={payment_data.get('event')}")
        
        # Обрабатываем webhook с проверкой IP
        success = PaymentService.process_webhook(payment_data, client_ip)
        
        if success:
            return Response({"status": "ok"}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "error"}, status=status.HTTP_400_BAD_REQUEST)
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return Response({"error": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def student_payments(request, student_id):
    """История платежей ученика"""
    if request.user.role not in [UserRole.ADMIN, UserRole.PARENT]:
        return Response(
            {"error": "Доступ запрещен"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Если родитель, проверяем что это его ребенок
    if request.user.role == UserRole.PARENT:
        try:
            student = CustomUser.objects.get(id=student_id)
            if student.parent_id != request.user.id:
                return Response(
                    {"error": "Доступ запрещен"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Ученик не найден"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Получаем платежи через подписки ученика
    payments = Payment.objects.filter(
        subscription__student_id=student_id
    ).select_related('subscription', 'parent').order_by('-created_at')
    
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
