from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from accounts.models import CustomUser, UserRole
from accounts.permissions import IsAdminRole
from groups.models import SchoolGroups
from sales.models import Order
from sales.services import OrderService
from subscriptions.models import Payment, Tariff
from subscriptions.payment_service import PaymentService
from subscriptions.api.serializers import PaymentSerializer, SubscriptionSerializer
from .serializers import OrderSerializer


class OrdersListAPIView(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = Order.objects.select_related('parent', 'student', 'created_by').prefetch_related('items', 'items__tariff', 'items__subscription', 'items__course', 'items__lesson', 'payments')
        status_filter = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(Q(parent__first_name__icontains=search) | Q(parent__last_name__icontains=search) | Q(student__first_name__icontains=search) | Q(student__last_name__icontains=search) | Q(items__title__icontains=search)).distinct()
        return qs.order_by('-created_at')


class OrderDetailAPIView(RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAdminRole]
    queryset = Order.objects.select_related('parent', 'student', 'created_by').prefetch_related('items', 'items__tariff', 'items__subscription', 'items__course', 'items__lesson', 'payments')


@api_view(['POST'])
def create_subscription_order(request):
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Только администратор может создавать заказы'}, status=status.HTTP_403_FORBIDDEN)
    try:
        student = CustomUser.objects.get(id=request.data.get('student_id'), role=UserRole.STUDENT)
        parent = CustomUser.objects.get(id=request.data.get('parent_id'), role=UserRole.PARENT)
        tariff = Tariff.objects.get(id=request.data.get('tariff_id'), is_active=True)
        group = SchoolGroups.objects.get(id=request.data.get('group_id')) if request.data.get('group_id') else None
        order, subscription = OrderService.create_subscription_order_new(student, parent, tariff, group=group, created_by=request.user, comment=request.data.get('notes', ''))
        payment = None
        payment_result = None
        if request.data.get('create_payment', True):
            payment_result = PaymentService.create_payment_for_order(order.id, parent.id, request.data.get('payment_method', 'cash'))
            payment = Payment.objects.get(id=payment_result['payment_id'])
            if request.data.get('confirm_payment') and payment.payment_method in ['cash', 'card', 'transfer']:
                payment = PaymentService.confirm_offline_payment(payment.id, confirmed_by=request.user)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    data = {'message': 'Заказ создан', 'order': OrderSerializer(order).data, 'subscription': SubscriptionSerializer(subscription).data}
    if payment:
        data['payment'] = PaymentSerializer(payment).data
    if payment_result and payment_result.get('payment_url'):
        data['payment_url'] = payment_result['payment_url']
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def create_order_payment(request, order_id):
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Только администратор может создавать платежи'}, status=status.HTTP_403_FORBIDDEN)
    try:
        result = PaymentService.create_payment_for_order(order_id, payment_method=request.data.get('payment_method', 'online'), amount=request.data.get('amount'))
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def confirm_payment(request, payment_id):
    try:
        payment = PaymentService.confirm_offline_payment(payment_id, confirmed_by=request.user)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'message': 'Оплата подтверждена', 'payment': PaymentSerializer(payment).data})


@api_view(['POST'])
def cancel_payment(request, payment_id):
    try:
        payment = PaymentService.cancel_payment(payment_id, canceled_by=request.user, reason=request.data.get('reason', ''))
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'message': 'Платеж отменен', 'payment': PaymentSerializer(payment).data})


class PaymentsListAPIView(ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminRole]
    queryset = Payment.objects.select_related('order', 'order__parent', 'order__student', 'parent', 'subscription').prefetch_related('order__items', 'order__items__subscription', 'order__items__tariff')


@api_view(['GET'])
def payment_status(request, payment_id):
    return Response(PaymentService.get_payment_status(payment_id))
