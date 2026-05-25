from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone
from ..models import Ticket, Message, TicketStatus
from .serializers import (
    TicketListSerializer, 
    TicketDetailSerializer, 
    MessageSerializer,
    CreateTicketSerializer,
    SendMessageSerializer
)
from accounts.models import UserRole


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для работы с тикетами (обращениями)
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == UserRole.ADMIN:
            # Админы видят все тикеты
            return Ticket.objects.all().select_related('parent', 'assigned_admin').prefetch_related('messages')
        elif user.role == UserRole.PARENT:
            # Родители видят только свои тикеты
            return Ticket.objects.filter(parent=user).select_related('assigned_admin').prefetch_related('messages')
        
        return Ticket.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TicketListSerializer
        return TicketDetailSerializer
    
    @action(detail=False, methods=['post'], url_path='create')
    def create_ticket(self, request):
        """
        Создать новое обращение (только для родителей)
        POST /api/v1/communication/tickets/create/
        Body: {
            "category": "payment",  // optional
            "custom_subject": "Своя тема",  // optional
            "message": "Текст первого сообщения"
        }
        """
        serializer = CreateTicketSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        
        return Response(
            TicketDetailSerializer(ticket, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], url_path='send-message')
    def send_message(self, request, pk=None):
        """
        Отправить сообщение в тикет
        POST /api/v1/communication/tickets/{id}/send-message/
        Body: {
            "content": "Текст сообщения"
        }
        """
        ticket = self.get_object()
        user = request.user
        
        # Проверка прав доступа
        if user.role == UserRole.PARENT:
            if ticket.parent_id != user.id:
                return Response(
                    {'error': 'Нет доступа к этому обращению'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role == UserRole.ADMIN:
            # Админ может отвечать в любой тикет
            pass
        else:
            return Response(
                {'error': 'Недостаточно прав'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Создаем сообщение
        message = Message.objects.create(
            ticket=ticket,
            sender=user,
            content=serializer.validated_data['content']
        )
        
        # Отправляем WebSocket событие получателю
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        if channel_layer:
            message_data = MessageSerializer(message).data
            
            # Определяем получателя
            if user.role == UserRole.ADMIN:
                # Админ отправил - уведомляем родителя
                recipient_id = ticket.parent_id
            else:
                # Родитель отправил - уведомляем админа
                recipient_id = ticket.assigned_admin_id
            
            if recipient_id:
                async_to_sync(channel_layer.group_send)(
                    f'user_{recipient_id}',
                    {
                        'type': 'new_message',
                        'message': message_data
                    }
                )
        
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], url_path='close')
    def close_ticket(self, request, pk=None):
        """
        Закрыть обращение (только для админов)
        POST /api/v1/communication/tickets/{id}/close/
        """
        ticket = self.get_object()
        user = request.user
        
        if user.role != UserRole.ADMIN:  # Только админы
            return Response(
                {'error': 'Только администраторы могут закрывать обращения'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            ticket.close(user)
            
            # Notify parent via WebSocket that ticket was closed
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'user_{ticket.parent_id}',
                    {
                        'type': 'ticket_closed',
                        'ticket': {
                            'id': ticket.id,
                            'status': ticket.status
                        }
                    }
                )
            
            return Response(
                TicketDetailSerializer(ticket, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='assign')
    def assign_ticket(self, request, pk=None):
        """
        Назначить обращение на себя (только для админов)
        POST /api/v1/communication/tickets/{id}/assign/
        """
        ticket = self.get_object()
        user = request.user
        
        if user.role != UserRole.ADMIN:  # Только админы
            return Response(
                {'error': 'Только администраторы могут назначать обращения'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            ticket.assign_to_admin(user)
            return Response(
                TicketDetailSerializer(ticket, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['patch'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Отметить все сообщения в тикете как прочитанные
        PATCH /api/v1/communication/tickets/{id}/mark-read/
        """
        ticket = self.get_object()
        user = request.user
        
        # Отмечаем как прочитанные только сообщения от другой стороны
        Message.objects.filter(
            ticket=ticket,
            is_read=False
        ).exclude(sender=user).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='chat-history')
    def chat_history(self, request):
        """
        Получить всю историю чата для родителя (все тикеты с сообщениями)
        GET /api/v1/communication/tickets/chat-history/
        """
        user = request.user
        
        if user.role != UserRole.PARENT:  # Только для родителей
            return Response(
                {'error': 'Этот endpoint доступен только для родителей'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tickets = Ticket.get_parent_chat_history(user)
        active_ticket = tickets.filter(
            status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_PARENT]
        ).first()
        
        serialized_tickets = []
        for ticket in tickets:
            serialized_tickets.append({
                'id': ticket.id,
                'category': ticket.category,
                'subject': ticket.subject or ticket.get_category_display(),
                'status': ticket.status,
                'created_at': ticket.created_at,
                'closed_at': ticket.closed_at,
                'messages': MessageSerializer(ticket.messages.all(), many=True).data
            })
        
        return Response({
            'tickets': serialized_tickets,
            'active_ticket': TicketDetailSerializer(active_ticket, context={'request': request}).data if active_ticket else None
        })
    
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """
        Получить количество непрочитанных сообщений
        GET /api/v1/communication/tickets/unread-count/
        """
        user = request.user
        
        if user.role == UserRole.ADMIN:
            count = Message.objects.filter(
                sender__role=UserRole.PARENT,
                is_read=False
            ).count()
        elif user.role == UserRole.PARENT:
            count = Message.objects.filter(
                ticket__parent=user,
                sender__role=UserRole.ADMIN,
                is_read=False
            ).count()
        else:
            count = 0
        
        return Response({'unread_count': count})


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для работы с сообщениями
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == UserRole.ADMIN:
            return Message.objects.all().select_related('ticket', 'sender')
        elif user.role == UserRole.PARENT:
            return Message.objects.filter(
                ticket__parent=user
            ).select_related('ticket', 'sender')
        
        return Message.objects.none()
    
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Отметить сообщение как прочитанное
        POST /api/v1/communication/messages/{id}/mark-read/
        """
        message = self.get_object()
        
        # Можно отметить только чужие сообщения
        if message.sender_id != request.user.id:
            message.mark_as_read()
        
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_200_OK
        )
