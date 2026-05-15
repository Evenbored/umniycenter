from rest_framework import serializers
from .models import Ticket, Message, TicketCategory, TicketStatus
from accounts.models import CustomUser


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_role = serializers.IntegerField(source='sender.role', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'ticket', 'sender_id', 'sender_name', 'sender_role', 'content', 
                  'created_at', 'is_read', 'read_at']
        read_only_fields = ['sender_id', 'sender_name', 'sender_role', 'created_at', 'is_read', 'read_at']


class TicketListSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.get_full_name', read_only=True)
    admin_name = serializers.CharField(source='assigned_admin.get_full_name', read_only=True, allow_null=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Ticket
        fields = ['id', 'parent', 'parent_name', 'assigned_admin', 'admin_name', 
                  'category', 'category_display', 'subject', 'status', 'status_display',
                  'created_at', 'last_message_at', 'closed_at', 'last_message', 'unread_count']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'id': last_msg.id,
                'content': last_msg.content,
                'sender_id': last_msg.sender_id,
                'created_at': last_msg.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        user = self.context['request'].user
        if user.role == 2:  # ADMIN
            return obj.unread_count_for_admin
        elif user.role == 3:  # PARENT
            return obj.unread_count_for_parent
        return 0


class TicketDetailSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    parent_name = serializers.CharField(source='parent.get_full_name', read_only=True)
    admin_name = serializers.CharField(source='assigned_admin.get_full_name', read_only=True, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Ticket
        fields = ['id', 'parent', 'parent_name', 'assigned_admin', 'admin_name', 
                  'category', 'category_display', 'subject', 'status', 'status_display',
                  'created_at', 'updated_at', 'last_message_at', 'closed_at', 'messages']


class CreateTicketSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=TicketCategory.choices, required=False, default=TicketCategory.OTHER)
    custom_subject = serializers.CharField(max_length=255, required=False, allow_blank=True)
    message = serializers.CharField(required=True, allow_blank=False)
    
    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Сообщение не может быть пустым")
        return value.strip()
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Проверяем, что пользователь - родитель
        if user.role != 3:  # PARENT
            raise serializers.ValidationError("Только родители могут создавать обращения")
        
        # Получаем или создаем активный тикет
        ticket, created = Ticket.get_or_create_active_ticket(user)
        
        # Если тикет новый, устанавливаем категорию и тему
        if created:
            ticket.category = validated_data.get('category', TicketCategory.OTHER)
            if validated_data.get('custom_subject'):
                ticket.subject = validated_data['custom_subject']
            ticket.save()
        
        # Создаем сообщение
        message = Message.objects.create(
            ticket=ticket,
            sender=user,
            content=validated_data['message']
        )
        
        return ticket


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=False)
    
    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Сообщение не может быть пустым")
        return value.strip()
