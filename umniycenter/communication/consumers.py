import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Ticket, Message, TicketStatus
from accounts.models import UserRole


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer для чата между родителями и администраторами
    """
    
    async def connect(self):
        self.user = self.scope["user"]
        
        # Проверка аутентификации
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Проверка роли (только родители и админы)
        if self.user.role not in [UserRole.ADMIN, UserRole.PARENT]:
            await self.close()
            return
        
        # Группа для пользователя (для получения личных сообщений)
        self.user_group_name = f'user_{self.user.id}'
        
        # Подключаемся к группе пользователя
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        # Если админ, подключаем к общей группе админов
        if self.user.role == UserRole.ADMIN:
            await self.channel_layer.group_add(
                'admins',
                self.channel_name
            )
        
        await self.accept()
        
        # Отправляем подтверждение подключения
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connected'
        }))
    
    async def disconnect(self, close_code):
        # Отключаемся от группы пользователя
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        
        # Если админ, отключаемся от группы админов
        if hasattr(self, 'user') and self.user.role == UserRole.ADMIN:
            await self.channel_layer.group_discard(
                'admins',
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Обработка входящих сообщений от клиента"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'send_message':
                await self.handle_send_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'mark_read':
                await self.handle_mark_read(data)
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def handle_send_message(self, data):
        """Обработка отправки сообщения"""
        content = data.get('content', '').strip()
        ticket_id = data.get('ticket_id')
        category = data.get('category')
        custom_subject = data.get('custom_subject')
        
        if not content:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Сообщение не может быть пустым'
            }))
            return
        
        # Создаем сообщение в БД
        result = await self.create_message(
            content=content,
            ticket_id=ticket_id,
            category=category,
            custom_subject=custom_subject
        )
        
        if result['error']:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': result['error']
            }))
            return
        
        message_data = result['message']
        ticket_data = result['ticket']
        
        # Отправляем подтверждение отправителю
        await self.send(text_data=json.dumps({
            'type': 'message_sent',
            'message': message_data
        }))
        
        # Если тикет был только что создан, отправляем уведомление
        if result['ticket_created']:
            await self.send(text_data=json.dumps({
                'type': 'ticket_created',
                'ticket': ticket_data
            }))
        
        # Получаем ID получателя. Для сообщений родителя администраторов уведомляем
        # только через общую группу admins ниже, иначе назначенный админ получает
        # одно и то же событие дважды: new_message и new_ticket_message.
        recipient_id = await self.get_recipient_id(ticket_data['id'])

        # Отправляем прямое сообщение получателю только для сообщений администратора
        # родителю. Родительские сообщения уходят всем администраторам через admins.
        if self.user.role != UserRole.PARENT and recipient_id and recipient_id != self.user.id:
            await self.channel_layer.group_send(
                f'user_{recipient_id}',
                {
                    'type': 'new_message',
                    'message': message_data
                }
            )
        
        # Если это сообщение от родителя, уведомляем всех админов
        if self.user.role == UserRole.PARENT:
            await self.channel_layer.group_send(
                'admins',
                {
                    'type': 'new_ticket_message',
                    'ticket_id': ticket_data['id'],
                    'message': message_data
                }
            )
    
    async def handle_typing(self, data):
        """Обработка индикатора печати"""
        ticket_id = data.get('ticket_id')
        is_typing = data.get('is_typing', False)
        
        if not ticket_id:
            return
        
        # Получаем ID получателя
        recipient_id = await self.get_recipient_id(ticket_id)
        
        if recipient_id:
            await self.channel_layer.group_send(
                f'user_{recipient_id}',
                {
                    'type': 'user_typing',
                    'ticket_id': ticket_id,
                    'user_id': self.user.id,
                    'is_typing': is_typing
                }
            )
    
    async def handle_mark_read(self, data):
        """Отметить сообщение как прочитанное"""
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_read(message_id)
    
    # Обработчики событий от channel layer
    
    async def new_message(self, event):
        """Отправка нового сообщения клиенту"""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))
    
    async def new_ticket_message(self, event):
        """Уведомление админов о новом сообщении в тикете"""
        # Не отправляем уведомление самому себе
        if event['message']['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'new_ticket_message',
                'ticket_id': event['ticket_id'],
                'message': event['message']
            }))
    
    async def ticket_closed(self, event):
        """Уведомление о закрытии тикета"""
        await self.send(text_data=json.dumps({
            'type': 'ticket_closed',
            'ticket': event['ticket']
        }))
    
    async def user_typing(self, event):
        """Индикатор печати"""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'ticket_id': event['ticket_id'],
            'user_id': event['user_id'],
            'is_typing': event['is_typing']
        }))
    
    # Database operations
    
    @database_sync_to_async
    def create_message(self, content, ticket_id=None, category=None, custom_subject=None):
        """Создать сообщение в БД"""
        try:
            ticket_created = False
            
            # Если ticket_id не указан, получаем или создаем активный тикет
            if not ticket_id:
                if self.user.role != UserRole.PARENT:  # Только родители могут создавать тикеты
                    return {'error': 'Только родители могут создавать обращения', 'message': None, 'ticket': None, 'ticket_created': False}
                
                ticket, ticket_created = Ticket.get_or_create_active_ticket(self.user)
                
                # Если тикет новый, устанавливаем категорию и тему
                if ticket_created:
                    ticket.category = category or 'other'
                    if custom_subject:
                        ticket.subject = custom_subject
                    ticket.save()
            else:
                try:
                    ticket = Ticket.objects.get(id=ticket_id)
                except Ticket.DoesNotExist:
                    return {'error': 'Обращение не найдено', 'message': None, 'ticket': None, 'ticket_created': False}
            
            # Проверка прав доступа
            if self.user.role == UserRole.PARENT:
                if ticket.parent_id != self.user.id:
                    return {'error': 'Нет доступа к этому обращению', 'message': None, 'ticket': None, 'ticket_created': False}
            elif self.user.role == UserRole.ADMIN:
                # Админ может отвечать в любой тикет
                pass
            else:
                return {'error': 'Недостаточно прав', 'message': None, 'ticket': None, 'ticket_created': False}
            
            # Создаем сообщение
            message = Message.objects.create(
                ticket=ticket,
                sender=self.user,
                content=content
            )
            
            return {
                'error': None,
                'message': self.serialize_message(message),
                'ticket': self.serialize_ticket(ticket),
                'ticket_created': ticket_created
            }
        
        except Exception as e:
            return {'error': str(e), 'message': None, 'ticket': None, 'ticket_created': False}
    
    @database_sync_to_async
    def get_recipient_id(self, ticket_id):
        """Получить ID получателя сообщения"""
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            
            if self.user.role == UserRole.PARENT:
                # Если админ назначен, отправляем ему, иначе None
                return ticket.assigned_admin_id
            else:  # ADMIN
                # Отправляем родителю
                return ticket.parent_id
        
        except Ticket.DoesNotExist:
            return None
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Отметить сообщение как прочитанное"""
        try:
            message = Message.objects.get(id=message_id)
            # Можно отметить только чужие сообщения
            if message.sender_id != self.user.id:
                message.mark_as_read()
        except Message.DoesNotExist:
            pass
    
    def serialize_message(self, message):
        """Сериализация сообщения"""
        return {
            'id': message.id,
            'ticket_id': message.ticket_id,
            'sender_id': message.sender_id,
            'sender_name': message.sender.get_full_name(),
            'content': message.content,
            'created_at': message.created_at.isoformat(),
            'is_read': message.is_read
        }
    
    def serialize_ticket(self, ticket):
        """Сериализация тикета"""
        return {
            'id': ticket.id,
            'parent_id': ticket.parent_id,
            'assigned_admin_id': ticket.assigned_admin_id,
            'category': ticket.category,
            'subject': ticket.subject or ticket.get_category_display(),
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat()
        }
