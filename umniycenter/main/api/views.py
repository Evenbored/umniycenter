from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from accounts.models import UserRole
from accounts.permissions import IsAdminRole
from ..models import ParticipantRequest
from .serializers import ParticipantRequestSerializer
from students.api.views import create_student_with_parent
from students.api.serializers import StudentListSerializer


class ParticipantRequestListAPIView(ListAPIView):
    serializer_class = ParticipantRequestSerializer
    permission_classes = [IsAdminRole]
    
    def get_queryset(self):
        return ParticipantRequest.objects.prefetch_related('courses').all()


@api_view(['PATCH'])
def mark_request_processed(request, pk):
    """Отметить заявку как обработанную"""
    if request.user.role != UserRole.ADMIN:
        return Response(
            {"error": "Только администратор может обрабатывать заявки"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        participant_request = ParticipantRequest.objects.get(pk=pk)
    except ParticipantRequest.DoesNotExist:
        return Response(
            {"error": "Заявка не найдена"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if participant_request.checked:
        return Response(
            {"error": "Заявка уже обработана"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    participant_request.checked = True
    participant_request.save()
    try:
        from sales.models import Lead, LeadStatus
        lead = Lead.from_participant_request(participant_request, assigned_to=request.user)
        lead.status = LeadStatus.CONTACTED
        lead.assigned_to = request.user
        lead.save(update_fields=['status', 'assigned_to', 'updated_at'])
    except Exception:
        pass
    
    serializer = ParticipantRequestSerializer(participant_request)
    return Response({
        "message": "Заявка отмечена как обработанная",
        "request": serializer.data
    })


@api_view(['POST'])
def create_student_from_request(request, pk):
    """Создать ученика и родителя после проверки предзаполненной формы администратором"""
    if request.user.role != UserRole.ADMIN:
        return Response(
            {"error": "Только администратор может создавать учеников"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        participant_request = ParticipantRequest.objects.prefetch_related('courses').get(pk=pk)
    except ParticipantRequest.DoesNotExist:
        return Response(
            {"error": "Заявка не найдена"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        payload = request.data.copy()
        payload.setdefault('password', f"student{participant_request.id}")
        payload.setdefault('parent_password', f"parent{participant_request.id}")
        payload.setdefault('source', participant_request.source)
        result, error = create_student_with_parent(payload)

        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Отмечаем заявку как обработанную
            participant_request.checked = True
            participant_request.save(update_fields=['checked'])
            try:
                from sales.models import Lead
                lead = Lead.from_participant_request(participant_request, assigned_to=request.user)
                lead.mark_converted(student=result["student"], parent=result.get("parent"))
            except Exception:
                pass

            return Response({
                "message": "Ученик и родитель успешно созданы",
                "student": StudentListSerializer(result["student"]).data,
                "parent_created": result["parent_created"],
                "request": ParticipantRequestSerializer(participant_request).data,
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {"error": f"Ошибка при создании: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
