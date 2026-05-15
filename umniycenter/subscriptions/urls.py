from django.urls import path
from . import api_views

app_name = 'subscriptions'

urlpatterns = [
    path('tariffs/', api_views.TariffListAPIView.as_view(), name='tariff_list'),
    path('tariffs/create/', api_views.create_tariff, name='tariff_create'),
    path('tariffs/<int:pk>/', api_views.TariffDetailAPIView.as_view(), name='tariff_detail'),
    path('students/<int:student_id>/subscriptions/', api_views.StudentSubscriptionsAPIView.as_view(), name='student_subscriptions'),
    path('students/<int:student_id>/attendance/', api_views.StudentAttendanceHistoryAPIView.as_view(), name='student_attendance'),
    path('create/', api_views.create_subscription, name='create_subscription'),
    path('quick-create/', api_views.quick_create_subscription, name='quick_create_subscription'),
    path('attendance/mark/', api_views.mark_attendance, name='mark_attendance'),
    path('attendance/<int:attendance_id>/cancel/', api_views.cancel_attendance, name='cancel_attendance'),
    
    # Платежи
    path('payments/', api_views.PaymentsListAPIView.as_view(), name='payment_list'),
    path('payments/create/', api_views.create_payment, name='create_payment'),
    path('payments/<int:payment_id>/confirm/', api_views.confirm_payment, name='payment_confirm'),
    path('payments/<int:payment_id>/cancel/', api_views.cancel_payment, name='payment_cancel'),
    path('payments/<int:payment_id>/status/', api_views.get_payment_status, name='payment_status'),
    path('payments/webhook/', api_views.yookassa_webhook, name='yookassa_webhook'),
    path('students/<int:student_id>/payments/', api_views.student_payments, name='student_payments'),
]
