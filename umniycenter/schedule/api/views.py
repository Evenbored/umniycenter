from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import CustomUser, UserRole
from courses.models import Courses
from groups.models import SchoolGroups
from accounts.permissions import IsAdminRole
from accounts.api.serializers import UserListSerializer
from students.models import StudentGroups
from ..models import GroupScheduleTemplate, Lesson, LessonParticipant, Schedule
from .serializers import GroupScheduleTemplateSerializer, LessonParticipantSerializer, LessonSerializer, ScheduleSerializer
from ..services import LessonService, generate_schedule_for_range, get_lesson_end_time, get_user_schedule


class MyScheduleAPIView(ListAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_user_schedule(self.request.user)


class CrmScheduleAPIView(ListAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        queryset = Lesson.objects.select_related("group", "group__course", "teacher", "course").prefetch_related("participants", "participants__student").order_by("starts_at")
        date_from = parse_date(self.request.query_params.get("date_from") or "")
        date_to = parse_date(self.request.query_params.get("date_to") or "")
        group_id = self.request.query_params.get("group")
        lesson_type = self.request.query_params.get("lesson_type")
        status_filter = self.request.query_params.get("status")

        if date_from:
            queryset = queryset.filter(starts_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(starts_at__date__lte=date_to)

        if group_id:
            queryset = queryset.filter(group_id=group_id)

        # Фильтрация по статусу с учетом actual_status
        if status_filter:
            if status_filter == 'completed':
                queryset = queryset.filter(ends_at__lt=timezone.now()).exclude(status='cancelled')
            elif status_filter == 'scheduled':
                queryset = queryset.filter(ends_at__gte=timezone.now(), status='scheduled')
            else:
                # Для cancelled и rescheduled фильтруем по полю status
                queryset = queryset.filter(status=status_filter)

        return queryset


class GroupScheduleTemplateListAPIView(ListAPIView):
    serializer_class = GroupScheduleTemplateSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        queryset = GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher").filter(group__isnull=False)
        group_id = self.request.query_params.get("group")

        if group_id:
            queryset = queryset.filter(group_id=group_id)

        return queryset.order_by("group__course__name", "group__number", "weekday", "start_time")


class GroupScheduleTemplateDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher").filter(group__isnull=False)
    serializer_class = GroupScheduleTemplateSerializer
    permission_classes = [IsAdminRole]


@api_view(["GET"])
def teacher_options(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Доступ запрещен"}, status=status.HTTP_403_FORBIDDEN)
    teachers = CustomUser.objects.filter(role=UserRole.TEACHER, is_active=True).order_by("last_name", "first_name", "id")
    return Response(UserListSerializer(teachers, many=True).data)


@api_view(["POST"])
def create_group_schedule_template(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать шаблоны расписания"}, status=status.HTTP_403_FORBIDDEN)

    serializer = GroupScheduleTemplateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    template = serializer.save()
    return Response({"message": "Шаблон расписания создан", "template": GroupScheduleTemplateSerializer(template).data}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def generate_crm_schedule(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может генерировать расписание"}, status=status.HTTP_403_FORBIDDEN)

    date_from = parse_date(request.data.get("date_from") or "")
    date_to = parse_date(request.data.get("date_to") or "")
    group_id = request.data.get("group_id") or None

    if not date_from or not date_to:
        return Response({"error": "Укажите период генерации"}, status=status.HTTP_400_BAD_REQUEST)

    if date_to < date_from:
        return Response({"error": "Дата окончания не может быть раньше даты начала"}, status=status.HTTP_400_BAD_REQUEST)

    created = generate_schedule_for_range(date_from, date_to, group_id=group_id)

    return Response({
        "message": f"Создано занятий: {len(created)}",
        "created_count": len(created),
        "lessons": LessonSerializer(created, many=True).data,
    })


@api_view(["POST"])
def create_crm_lesson(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать занятия"}, status=status.HTTP_403_FORBIDDEN)

    lesson_type = request.data.get("lesson_type") or Lesson.LessonType.GROUP
    classdate_start = parse_datetime(request.data.get("starts_at") or request.data.get("classdateStart") or "")
    ends_at = parse_datetime(request.data.get("ends_at") or "")
    lessons_count = int(request.data.get("lessons_count") or 2)
    teacher_id = request.data.get("teacher")

    legacy_map = {'regular': Lesson.LessonType.GROUP if request.data.get('group') else Lesson.LessonType.INDIVIDUAL, 'single': Lesson.LessonType.SINGLE_GROUP if request.data.get('group') else Lesson.LessonType.SINGLE_INDIVIDUAL}
    lesson_type = legacy_map.get(lesson_type, lesson_type)
    if lesson_type not in dict(Lesson.LessonType.choices):
        return Response({"error": "Выберите корректный тип занятия"}, status=status.HTTP_400_BAD_REQUEST)

    if not classdate_start:
        return Response({"error": "Укажите дату и время начала"}, status=status.HTTP_400_BAD_REQUEST)

    if timezone.is_naive(classdate_start):
        classdate_start = timezone.make_aware(classdate_start)

    if lessons_count not in (1, 2):
        return Response({"error": "Занятие может длиться только 1 или 2 академических часа"}, status=status.HTTP_400_BAD_REQUEST)

    if not ends_at:
        from datetime import datetime
        ends_at = timezone.make_aware(datetime.combine(classdate_start.date(), get_lesson_end_time(classdate_start.time(), lessons_count)))

    selected_student_ids = request.data.get("students") or []
    if not isinstance(selected_student_ids, list):
        selected_student_ids = []

    try:
        teacher = CustomUser.objects.get(id=teacher_id, role=UserRole.TEACHER)
        group = SchoolGroups.objects.get(id=request.data.get('group')) if request.data.get('group') else None
        course = group.course if group else Courses.objects.get(id=request.data.get('course'))
        participant_ids = selected_student_ids or request.data.get('participants') or ([request.data.get('student')] if request.data.get('student') else [])
        participants = list(CustomUser.objects.filter(id__in=participant_ids, role=UserRole.STUDENT))
        lesson = LessonService.create_lesson(lesson_type=lesson_type, group=group, course=course, teacher=teacher, starts_at=classdate_start, ends_at=ends_at, participants=participants, created_by=request.user)
        if lesson.is_single:
            from sales.services import OrderService
            amount = request.data.get("single_lesson_amount") or request.data.get("amount")
            if amount:
                order = OrderService.create_single_lesson_order(
                    lesson=lesson,
                    student=participants[0] if participants else None,
                    amount=amount,
                    payment_method=request.data.get("single_lesson_payment_method", "cash"),
                    paid=request.data.get("single_lesson_paid", True) is not False,
                    created_by=request.user,
                    comment="Продажа разового занятия через API",
                )
                item = order.items.first()
                if item:
                    lesson.participants.update(order_item=item)
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "Занятие создано", "lesson": LessonSerializer(lesson).data}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def student_options(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Доступ запрещен"}, status=status.HTTP_403_FORBIDDEN)
    course_id = request.query_params.get("course")
    subscription_type = request.query_params.get("subscription_type")
    group_id = request.query_params.get("group")

    students = CustomUser.objects.filter(role=UserRole.STUDENT, is_active=True)

    if group_id:
        students = students.filter(studentgroups__group_id=group_id)

    if course_id:
        students = students.filter(
            subscriptions__status='active',
            subscriptions__tariff__course_id=course_id,
            subscriptions__end_date__gte=timezone.now().date(),
        )

    if subscription_type:
        students = students.filter(subscriptions__tariff__subscription_type=subscription_type)

    students = students.distinct().order_by("last_name", "first_name", "id")
    return Response(UserListSerializer(students, many=True).data)


@api_view(["PATCH"])
def cancel_lesson(request, lesson_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может отменять занятия"}, status=status.HTTP_403_FORBIDDEN)

    try:
        lesson = Lesson.objects.get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)

    # Проверяем, есть ли отметки посещаемости
    try:
        attendance_count = LessonParticipant.objects.filter(lesson=lesson, lessons_charged=True).count()
        
        if attendance_count > 0:
            return Response({
                "error": f"Нельзя отменить занятие с отметками посещаемости. Сначала отмените {attendance_count} отметок."
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        pass

    LessonService.cancel_lesson(lesson, (request.data.get("reason") or "").strip(), request.user)

    return Response({"message": "Занятие отменено", "lesson": LessonSerializer(lesson).data})


@api_view(["PATCH"])
def reschedule_lesson(request, lesson_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может переносить занятия"}, status=status.HTTP_403_FORBIDDEN)

    try:
        lesson = Lesson.objects.get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)

    new_start = parse_datetime(request.data.get("starts_at") or request.data.get("classdateStart") or "")
    lessons_count = request.data.get("lessons_count")
    lesson_type = request.data.get("lesson_type") or lesson.lesson_type
    
    if not new_start:
        return Response({"error": "Укажите новую дату и время начала"}, status=status.HTTP_400_BAD_REQUEST)

    if timezone.is_naive(new_start):
        new_start = timezone.make_aware(new_start)

    # Если lessons_count не передан, используем значение по умолчанию 2
    if lessons_count is None:
        lessons_count = 2
    else:
        lessons_count = int(lessons_count)

    if lessons_count not in (1, 2):
        return Response({"error": "Занятие может длиться только 1 или 2 академических часа"}, status=status.HTTP_400_BAD_REQUEST)

    if lesson_type not in dict(Lesson.LessonType.choices):
        return Response({"error": "Выберите корректный тип занятия"}, status=status.HTTP_400_BAD_REQUEST)

    from datetime import datetime
    new_end = parse_datetime(request.data.get('ends_at') or '') or timezone.make_aware(datetime.combine(new_start.date(), get_lesson_end_time(new_start.time(), lessons_count)))
    LessonService.reschedule_lesson(lesson, new_start, new_end, (request.data.get("reason") or "").strip(), request.user)
    return Response({"message": "Занятие перенесено", "lesson": LessonSerializer(lesson).data})


@api_view(["GET"])
def lesson_attendance_context(request, lesson_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может просматривать посещаемость занятия"}, status=status.HTTP_403_FORBIDDEN)

    try:
        lesson = Lesson.objects.select_related("group", "group__course", "teacher", "course").prefetch_related('participants', 'participants__student', 'participants__subscription', 'participants__subscription__tariff', 'participants__order_item').get(id=lesson_id)
    except Lesson.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "lesson": LessonSerializer(lesson).data,
        "participants": LessonParticipantSerializer(lesson.participants.all(), many=True).data,
    })


@api_view(["PATCH"])
def mark_participant_attendance(request, participant_id):
    if request.user.role not in [UserRole.ADMIN, UserRole.TEACHER]:
        return Response({"error": "Только администратор или учитель могут отмечать посещаемость"}, status=status.HTTP_403_FORBIDDEN)
    try:
        participant = LessonParticipant.objects.select_related('lesson', 'student', 'subscription').get(id=participant_id)
    except LessonParticipant.DoesNotExist:
        return Response({"error": "Участник занятия не найден"}, status=status.HTTP_404_NOT_FOUND)
    try:
        participant = LessonService.mark_participant_attendance(participant, request.data.get('attendance_status') or request.data.get('status'), request.data.get('lessons_to_charge') or request.data.get('lessons_count') or 0, request.user, request.data.get('notes', ''))
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "Посещаемость отмечена", "participant": LessonParticipantSerializer(participant).data})


@api_view(["POST"])
def cancel_participant_attendance(request, participant_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может отменять посещаемость"}, status=status.HTTP_403_FORBIDDEN)
    try:
        participant = LessonParticipant.objects.select_related('lesson', 'student', 'subscription').get(id=participant_id)
    except LessonParticipant.DoesNotExist:
        return Response({"error": "Участник занятия не найден"}, status=status.HTTP_404_NOT_FOUND)
    participant = LessonService.cancel_participant_attendance(participant, request.user)
    return Response({"message": "Отметка посещаемости отменена", "participant": LessonParticipantSerializer(participant).data})
