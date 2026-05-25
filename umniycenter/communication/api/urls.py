from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, MessageViewSet

router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]
