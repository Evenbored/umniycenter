from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from subscriptions import views as payment_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('umniycenter.api_urls', namespace='api')),
    path('', include('main.urls', namespace='main')),
    path('', include('groups.urls', namespace='groups')),
    path('', include('accounts.urls', namespace='accounts')),
    path('', include('homework.urls', namespace='homework')),
    path('', include('students.urls', namespace='students')),
    path('', include('schedule.urls', namespace='schedule')),
    path('', include('crm.urls', namespace='crm')),
    
    # Страницы оплаты
    path('payment/success/', payment_views.payment_success, name='payment_success'),
    path('payment/failed/', payment_views.payment_failed, name='payment_failed'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
