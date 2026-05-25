from django.urls import path
from .api import views

app_name = 'subscriptions'

urlpatterns = [
    path('tariffs/', views.TariffListAPIView.as_view(), name='tariff_list'),
    path('tariffs/create/', views.create_tariff, name='tariff_create'),
    path('tariffs/<int:pk>/', views.TariffDetailAPIView.as_view(), name='tariff_detail'),
    path('students/<int:student_id>/subscriptions/', views.StudentSubscriptionsAPIView.as_view(), name='student_subscriptions'),
    path('students/<int:student_id>/attendance/', views.StudentAttendanceHistoryAPIView.as_view(), name='student_attendance'),
    path('create/', views.create_subscription, name='create_subscription'),
    path('quick-create/', views.quick_create_subscription, name='quick_create_subscription'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/<int:attendance_id>/cancel/', views.cancel_attendance, name='cancel_attendance'),
    
    # Платежи
    path('payments/', views.PaymentsListAPIView.as_view(), name='payment_list'),
    path('payments/create/', views.create_payment, name='create_payment'),
    path('payments/<int:payment_id>/confirm/', views.confirm_payment, name='payment_confirm'),
    path('payments/<int:payment_id>/cancel/', views.cancel_payment, name='payment_cancel'),
    path('payments/<int:payment_id>/status/', views.get_payment_status, name='payment_status'),
    path('payments/webhook/', views.yookassa_webhook, name='yookassa_webhook'),
    path('students/<int:student_id>/payments/', views.student_payments, name='student_payments'),
]
