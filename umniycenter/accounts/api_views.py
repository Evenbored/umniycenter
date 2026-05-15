from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.decorators import api_view
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q, Count
from django.utils import timezone
import re
from rest_framework.permissions import IsAuthenticated
from accounts.models import CustomUser, UserRole, TeacherProfile
from accounts.permissions import IsAdminRole, IsAdminTeacherOrStudentRole
from groups.models import SchoolGroups
from schedule.models import Schedule

from .serializers import CurrentUserSerializer, ParentListSerializer, ParentUpdateSerializer, UserListSerializer


class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data)

class UserListAPIView(ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAdminRole]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "role",
        "is_active",
        "sex",
    ]

    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
    ]

    ordering_fields = [
        "id",
        "first_name",
        "last_name",
        "email",
        "date_joined",
    ]

    ordering = ["id"]

    def get_queryset(self):
        return CustomUser.objects.all()


class TeachersListAPIView(ListAPIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        teachers = CustomUser.objects.filter(role=UserRole.TEACHER).annotate(
            groups_count=Count('schoolgroups', distinct=True)
        ).order_by('last_name', 'first_name')

        search = request.query_params.get('search', '').strip()
        if search:
            teachers = teachers.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search)
            )

        data = []
        for teacher in teachers:
            data.append({
                'id': teacher.id,
                'full_name': teacher.get_full_name() or teacher.username,
                'username': teacher.username,
                'phone': teacher.phone,
                'email': teacher.email,
                'city': teacher.city,
                'country': teacher.country,
                'sex': teacher.sex,
                'is_active': teacher.is_active,
                'date_joined': teacher.date_joined.strftime('%d.%m.%Y') if teacher.date_joined else '',
                'groups_count': teacher.groups_count,
            })

        return Response(data)


@api_view(['GET', 'PATCH'])
def teacher_detail(request, teacher_id):
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)

    try:
        teacher = CustomUser.objects.get(id=teacher_id, role=UserRole.TEACHER)
    except CustomUser.DoesNotExist:
        return Response({'error': 'Учитель не найден'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        groups = SchoolGroups.objects.filter(teacher=teacher, is_active=True).select_related('course')
        groups_data = [
            {
                'id': group.id,
                'name': str(group),
                'course': group.course.name,
            }
            for group in groups
        ]

        # Получаем ближайшие занятия
        today = timezone.now()
        schedule = Schedule.objects.filter(
            teacher=teacher,
            classdateStart__gte=today
        ).select_related('group', 'group__course').order_by('classdateStart')[:10]

        schedule_data = [
            {
                'id': lesson.id,
                'group': str(lesson.group),
                'course': lesson.group.course.name,
                'date': lesson.classdateStart.strftime('%d.%m.%Y'),
                'start_time': lesson.classdateStart.strftime('%H:%M'),
                'end_time': lesson.classdateEnd.strftime('%H:%M'),
            }
            for lesson in schedule
        ]

        return Response({
            'id': teacher.id,
            'full_name': teacher.get_full_name() or teacher.username,
            'username': teacher.username,
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'phone': teacher.phone,
            'email': teacher.email,
            'city': teacher.city,
            'country': teacher.country,
            'sex': teacher.sex,
            'is_active': teacher.is_active,
            'date_joined': teacher.date_joined.strftime('%d.%m.%Y') if teacher.date_joined else '',
            'groups': groups_data,
            'schedule': schedule_data,
        })

    elif request.method == 'PATCH':
        data = request.data

        # Валидация обязательных полей
        first_name = data.get('first_name', '').strip() if data.get('first_name') else ''
        last_name = data.get('last_name', '').strip() if data.get('last_name') else ''
        username = data.get('username', '').strip() if data.get('username') else ''
        
        if not first_name or not last_name or not username:
            return Response({'error': 'Заполните обязательные поля'}, status=status.HTTP_400_BAD_REQUEST)

        # Валидация телефона
        phone = data.get('phone', '').strip() if data.get('phone') else ''
        if phone and not re.match(r'^\+7\d{10}$', phone):
            return Response({'error': 'Телефон должен быть в формате +7XXXXXXXXXX'}, status=status.HTTP_400_BAD_REQUEST)

        # Валидация email
        email = data.get('email', '').strip() if data.get('email') else ''
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({'error': 'Введите корректный email'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка уникальности username
        if CustomUser.objects.filter(username=username).exclude(id=teacher_id).exists():
            return Response({'error': 'Пользователь с таким логином уже существует'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка уникальности email
        if email and CustomUser.objects.filter(email=email).exclude(id=teacher_id).exists():
            return Response({'error': 'Пользователь с таким email уже существует'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка уникальности телефона
        if phone and CustomUser.objects.filter(phone=phone).exclude(id=teacher_id).exists():
            return Response({'error': 'Пользователь с таким номером телефона уже существует'}, status=status.HTTP_400_BAD_REQUEST)

        # Обновление данных
        teacher.first_name = first_name
        teacher.last_name = last_name
        teacher.username = username
        teacher.phone = phone or None
        teacher.email = email or None
        teacher.city = data.get('city', '').strip() if data.get('city') else None
        teacher.country = data.get('country', '').strip() if data.get('country') else None
        teacher.sex = data.get('sex', False)
        teacher.is_active = data.get('is_active', True)

        try:
            teacher.save()
        except Exception as e:
            return Response({'error': f'Ошибка сохранения: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'id': teacher.id,
            'full_name': teacher.get_full_name() or teacher.username,
            'username': teacher.username,
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'phone': teacher.phone,
            'email': teacher.email,
            'city': teacher.city,
            'country': teacher.country,
            'sex': teacher.sex,
            'is_active': teacher.is_active,
            'date_joined': teacher.date_joined.strftime('%d.%m.%Y') if teacher.date_joined else '',
        })


@api_view(['POST'])
def create_teacher(request):
    if request.user.role != UserRole.ADMIN:
        return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data

    # Валидация обязательных полей
    first_name = data.get('first_name', '').strip() if data.get('first_name') else ''
    last_name = data.get('last_name', '').strip() if data.get('last_name') else ''
    username = data.get('username', '').strip() if data.get('username') else ''
    password = data.get('password', '').strip() if data.get('password') else ''
    
    if not first_name or not last_name or not username or not password:
        return Response({'error': 'Заполните все обязательные поля'}, status=status.HTTP_400_BAD_REQUEST)

    # Валидация телефона
    phone = data.get('phone', '').strip() if data.get('phone') else ''
    if phone and not re.match(r'^\+7\d{10}$', phone):
        return Response({'error': 'Телефон должен быть в формате +7XXXXXXXXXX'}, status=status.HTTP_400_BAD_REQUEST)

    # Валидация email
    email = data.get('email', '').strip() if data.get('email') else ''
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return Response({'error': 'Введите корректный email'}, status=status.HTTP_400_BAD_REQUEST)

    # Проверка уникальности username
    if CustomUser.objects.filter(username=username).exists():
        return Response({'error': 'Пользователь с таким логином уже существует'}, status=status.HTTP_400_BAD_REQUEST)

    # Проверка уникальности email
    if email and CustomUser.objects.filter(email=email).exists():
        return Response({'error': 'Пользователь с таким email уже существует'}, status=status.HTTP_400_BAD_REQUEST)

    # Проверка уникальности телефона
    if phone and CustomUser.objects.filter(phone=phone).exists():
        return Response({'error': 'Пользователь с таким номером телефона уже существует'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        teacher = CustomUser.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            password=password,
            phone=phone or None,
            email=email or None,
            role=UserRole.TEACHER,
            sex=data.get('sex', False),
        )
        teacher.city = data.get('city', '').strip() if data.get('city') else None
        teacher.country = data.get('country', '').strip() if data.get('country') else None
        teacher.save()

        # Создаем профиль учителя
        TeacherProfile.objects.get_or_create(user=teacher)

        return Response({
            'id': teacher.id,
            'full_name': teacher.get_full_name() or teacher.username,
            'username': teacher.username,
            'message': 'Учитель успешно создан'
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': f'Ошибка создания учителя: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)



class ParentsListAPIView(ListAPIView):
    serializer_class = ParentListSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        queryset = CustomUser.objects.filter(role=UserRole.PARENT).prefetch_related(
            "parent_profile__students",
            "parent_profile__students__user",
        )
        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(parent_profile__students__user__first_name__icontains=search) |
                Q(parent_profile__students__user__last_name__icontains=search)
            ).distinct()

        return queryset.order_by("last_name", "first_name", "id")

@api_view(["PATCH"])
def update_parent(request, parent_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может редактировать родителей"}, status=status.HTTP_403_FORBIDDEN)

    try:
        parent = CustomUser.objects.get(id=parent_id, role=UserRole.PARENT)
    except CustomUser.DoesNotExist:
        return Response({"error": "Родитель не найден"}, status=status.HTTP_404_NOT_FOUND)

    serializer = ParentUpdateSerializer(parent, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    updated_parent = CustomUser.objects.prefetch_related(
        "parent_profile__students",
        "parent_profile__students__user",
    ).get(id=parent.id)
    return Response({
        "message": "Данные родителя обновлены",
        "parent": ParentListSerializer(updated_parent).data,
    })
