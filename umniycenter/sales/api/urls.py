from django.urls import path

from .views import OrdersListAPIView, OrderDetailAPIView, PaymentsListAPIView, cancel_payment, confirm_payment, create_order_payment, create_subscription_order, payment_status

urlpatterns = [
    path('orders/', OrdersListAPIView.as_view(), name='sales_orders'),
    path('orders/subscription/', create_subscription_order, name='sales_order_subscription'),
    path('orders/<int:pk>/', OrderDetailAPIView.as_view(), name='sales_order_detail'),
    path('orders/<int:order_id>/payments/', create_order_payment, name='sales_order_payment_create'),
    path('payments/', PaymentsListAPIView.as_view(), name='sales_payments'),
    path('payments/<int:payment_id>/confirm/', confirm_payment, name='sales_payment_confirm'),
    path('payments/<int:payment_id>/cancel/', cancel_payment, name='sales_payment_cancel'),
    path('payments/<int:payment_id>/status/', payment_status, name='sales_payment_status'),
]
