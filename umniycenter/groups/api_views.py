from django.core.cache import cache
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserRole
from accounts.permissions import IsAdminOrTeacherRole
from .models import SchoolGroups
from .serializers import SchoolGroupSerializer


class MyGroupsAPIView(ListAPIView):
    serializer_class = SchoolGroupSerializer
    permission_classes = [IsAdminOrTeacherRole]

    def get_queryset(self):
        user = self.request.user

        if user.role == UserRole.TEACHER:
            queryset = SchoolGroups.objects.filter(teacher=user)

        elif user.role == UserRole.ADMIN:
            queryset = SchoolGroups.objects.all()

        else:
            return SchoolGroups.objects.none()

        queryset = queryset.select_related("course", "teacher").annotate(
            students_count=Count("studentgroups", distinct=True)
        )

        search = self.request.query_params.get("search")
        teacher = self.request.query_params.get("teacher")
        status = self.request.query_params.get("status")
        ordering = self.request.query_params.get("ordering")

        if search:
            queryset = queryset.filter(
                Q(number__icontains=search)
                | Q(course__name__icontains=search)
                | Q(teacher__first_name__icontains=search)
                | Q(teacher__last_name__icontains=search)
            )

        if teacher:
            queryset = queryset.filter(teacher_id=teacher)

        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "archive":
            queryset = queryset.filter(is_active=False)

        ordering_map = {
            "name_az": ("course__name", "number"),
            "students_desc": ("-students_count", "course__name", "number"),
            "students_asc": ("students_count", "course__name", "number"),
        }

        return queryset.order_by(*ordering_map.get(ordering, ("course__name", "number")))


class GroupsCountAPIView(APIView):
    permission_classes = [IsAdminOrTeacherRole]

    def get(self, request):
        if request.user.role == UserRole.ADMIN:
            count = SchoolGroups.objects.count()
            return Response({"count": count})

        if request.user.role != UserRole.TEACHER:
            return Response({"count": 0})

        key = f"user:{request.user.id}:groups_count"
        count = cache.get(key)

        if count is None:
            count = SchoolGroups.objects.filter(teacher=request.user).count()
            cache.set(key, count, 60)

        return Response({"count": count})


@api_view(["POST"])
def create_group(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать группы"}, status=status.HTTP_403_FORBIDDEN)

    serializer = SchoolGroupSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    group = serializer.save()
    
    # Создаем шаблон расписания, если указано стандартное время
    default_time = request.data.get("default_lesson_time")
    default_duration = request.data.get("default_lesson_duration")
    
    if default_time:
        from schedule.models import GroupScheduleTemplate
        from datetime import datetime
        
        try:
            # Парсим время
            time_obj = datetime.strptime(default_time, "%H:%M").time()
            
            # Определяем количество занятий на основе длительности
            lessons_count = 2  # по умолчанию 90 минут
            if default_duration:
                duration_int = int(default_duration)
                if duration_int == 45:
                    lessons_count = 1
                elif duration_int == 120:
                    lessons_count = 2
            
            # Создаем шаблон для каждого дня недели (можно настроить)
            # Пока создаем один шаблон на понедельник как пример
            GroupScheduleTemplate.objects.create(
                group=group,
                weekday=0,  # Понедельник
                start_time=time_obj,
                lessons_count=lessons_count,
                is_active=True
            )
        except Exception:
            pass  # Игнорируем ошибки создания шаблона
    
    created_group = (
        SchoolGroups.objects
        .select_related("course", "teacher")
        .annotate(students_count=Count("studentgroups", distinct=True))
        .get(id=group.id)
    )

    return Response({
        "message": "Группа создана",
        "group": SchoolGroupSerializer(created_group).data,
    }, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
def update_group(request, group_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может редактировать группы"}, status=status.HTTP_403_FORBIDDEN)

    try:
        group = SchoolGroups.objects.get(id=group_id)
    except SchoolGroups.DoesNotExist:
        return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

    serializer = SchoolGroupSerializer(group, data=request.data, partial=True)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    updated_group = (
        SchoolGroups.objects
        .select_related("course", "teacher")
        .annotate(students_count=Count("studentgroups", distinct=True))
        .get(id=group.id)
    )

    return Response({
        "message": "Группа обновлена",
        "group": SchoolGroupSerializer(updated_group).data,
    })
