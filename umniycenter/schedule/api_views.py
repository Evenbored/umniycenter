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
from accounts.serializers import UserListSerializer
from students.models import StudentGroups
from .models import GroupScheduleTemplate, Schedule
from .serializers import GroupScheduleTemplateSerializer, ScheduleSerializer
from .services import generate_schedule_for_range, get_lesson_end_time, get_user_schedule


class MyScheduleAPIView(ListAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_user_schedule(self.request.user)


class CrmScheduleAPIView(ListAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        queryset = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").order_by("classdateStart")
        date_from = parse_date(self.request.query_params.get("date_from") or "")
        date_to = parse_date(self.request.query_params.get("date_to") or "")
        group_id = self.request.query_params.get("group")
        lesson_type = self.request.query_params.get("lesson_type")
        status_filter = self.request.query_params.get("status")

        if date_from:
            queryset = queryset.filter(classdateStart__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(classdateStart__date__lte=date_to)

        if group_id:
            queryset = queryset.filter(group_id=group_id)

        # Фильтрация по статусу с учетом actual_status
        if status_filter:
            if status_filter == 'completed':
                # Для "Прошло" - фильтруем занятия, которые уже закончились
                from django.utils import timezone
                from datetime import datetime
                now = timezone.now()
                # Получаем все занятия и фильтруем по времени окончания
                completed_ids = []
                for lesson in queryset:
                    end_datetime = datetime.combine(lesson.classdateStart.date(), lesson.classdateEnd)
                    end_datetime_aware = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
                    if end_datetime_aware < now and lesson.status != 'cancelled':
                        completed_ids.append(lesson.id)
                queryset = queryset.filter(id__in=completed_ids)
            elif status_filter == 'scheduled':
                # Для "Запланировано" - только те, что еще не прошли и не отменены/перенесены
                from django.utils import timezone
                from datetime import datetime
                now = timezone.now()
                scheduled_ids = []
                for lesson in queryset:
                    end_datetime = datetime.combine(lesson.classdateStart.date(), lesson.classdateEnd)
                    end_datetime_aware = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
                    if end_datetime_aware >= now and lesson.status == 'scheduled':
                        scheduled_ids.append(lesson.id)
                queryset = queryset.filter(id__in=scheduled_ids)
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
        "lessons": ScheduleSerializer(created, many=True).data,
    })


@api_view(["POST"])
def create_crm_lesson(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать занятия"}, status=status.HTTP_403_FORBIDDEN)

    lesson_type = request.data.get("lesson_type") or Schedule.LESSON_TYPE_REGULAR
    classdate_start = parse_datetime(request.data.get("classdateStart") or "")
    lessons_count = int(request.data.get("lessons_count") or 2)
    teacher_id = request.data.get("teacher")

    if lesson_type not in dict(Schedule.LESSON_TYPE_CHOICES):
        return Response({"error": "Выберите корректный тип занятия"}, status=status.HTTP_400_BAD_REQUEST)

    if not classdate_start:
        return Response({"error": "Укажите дату и время начала"}, status=status.HTTP_400_BAD_REQUEST)

    if timezone.is_naive(classdate_start):
        classdate_start = timezone.make_aware(classdate_start)

    if lessons_count not in (1, 2):
        return Response({"error": "Занятие может длиться только 1 или 2 академических часа"}, status=status.HTTP_400_BAD_REQUEST)

    payload = {
        "lesson_type": lesson_type,
        "classdateStart": classdate_start,
        "classdateEnd": get_lesson_end_time(classdate_start.time(), lessons_count),
        "teacher": teacher_id,
        "status": "scheduled",
        "is_single": lesson_type == Schedule.LESSON_TYPE_SINGLE,
    }

    selected_student_ids = request.data.get("students") or []
    if not isinstance(selected_student_ids, list):
        selected_student_ids = []

    if request.data.get("group"):
        payload["group"] = request.data.get("group")
    else:
        payload["student"] = request.data.get("student")
        payload["course"] = request.data.get("course")

    serializer = ScheduleSerializer(data=payload)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        lesson = serializer.save()
        lesson.full_clean()
        lesson.save()
        if lesson.group_id and selected_student_ids:
            allowed_students = CustomUser.objects.filter(
                id__in=selected_student_ids,
                role=UserRole.STUDENT,
                subscriptions__status='active',
                subscriptions__tariff__course=lesson.group.course,
                subscriptions__tariff__subscription_type='group',
                subscriptions__end_date__gte=timezone.now().date(),
            ).distinct()
            lesson.students.set(allowed_students)
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "Занятие создано", "lesson": ScheduleSerializer(lesson).data}, status=status.HTTP_201_CREATED)


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
        lesson = Schedule.objects.get(id=lesson_id)
    except Schedule.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)

    # Проверяем, есть ли отметки посещаемости
    try:
        from subscriptions.models import LessonAttendance
        attendance_count = LessonAttendance.objects.filter(schedule=lesson).count()
        
        if attendance_count > 0:
            return Response({
                "error": f"Нельзя отменить занятие с отметками посещаемости. Сначала отмените {attendance_count} отметок."
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        pass

    lesson.status = "cancelled"
    lesson.cancel_reason = (request.data.get("reason") or "").strip()
    lesson.save(update_fields=["status", "cancel_reason"])

    return Response({"message": "Занятие отменено", "lesson": ScheduleSerializer(lesson).data})


@api_view(["PATCH"])
def reschedule_lesson(request, lesson_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может переносить занятия"}, status=status.HTTP_403_FORBIDDEN)

    try:
        lesson = Schedule.objects.get(id=lesson_id)
    except Schedule.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)

    new_start = parse_datetime(request.data.get("classdateStart") or "")
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

    if lesson_type not in dict(Schedule.LESSON_TYPE_CHOICES):
        return Response({"error": "Выберите корректный тип занятия"}, status=status.HTTP_400_BAD_REQUEST)

    lesson.lesson_type = lesson_type
    lesson.is_single = lesson_type == Schedule.LESSON_TYPE_SINGLE

    if request.data.get("group") or lesson.group_id:
        group_id = request.data.get("group") or (lesson.group_id if lesson.group_id else None)
        if not group_id:
            return Response({"error": "Выберите группу"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            lesson.group = SchoolGroups.objects.get(id=group_id)
        except SchoolGroups.DoesNotExist:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)
        lesson.student = None
        lesson.course = lesson.group.course
    else:
        student_id = request.data.get("student") or lesson.student_id
        course_id = request.data.get("course") or lesson.course_id
        if not student_id or not course_id:
            return Response({"error": "Выберите ученика и курс"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            lesson.student = CustomUser.objects.get(id=student_id, role=UserRole.STUDENT)
        except CustomUser.DoesNotExist:
            return Response({"error": "Ученик не найден"}, status=status.HTTP_404_NOT_FOUND)
        try:
            lesson.course = Courses.objects.get(id=course_id)
        except Courses.DoesNotExist:
            return Response({"error": "Курс не найден"}, status=status.HTTP_404_NOT_FOUND)
        lesson.group = None

    if not lesson.original_classdateStart:
        lesson.original_classdateStart = lesson.classdateStart
        lesson.original_classdateEnd = lesson.classdateEnd

    lesson.classdateStart = new_start
    lesson.classdateEnd = get_lesson_end_time(new_start.time(), lessons_count)
    lesson.status = "rescheduled"
    lesson.reschedule_reason = (request.data.get("reason") or "").strip()
    lesson.save()

    return Response({"message": "Занятие перенесено", "lesson": ScheduleSerializer(lesson).data})


@api_view(["GET"])
def lesson_attendance_context(request, lesson_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может просматривать посещаемость занятия"}, status=status.HTTP_403_FORBIDDEN)

    try:
        lesson = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").get(id=lesson_id)
    except Schedule.DoesNotExist:
        return Response({"error": "Занятие не найдено"}, status=status.HTTP_404_NOT_FOUND)

    memberships = []
    individual_student = None
    source_students = []

    if lesson.group:
        explicit_students = list(lesson.students.all().order_by("last_name", "first_name"))
        if explicit_students:
            source_students = explicit_students
        else:
            memberships = (
                StudentGroups.objects
                .select_related("student")
                .filter(group=lesson.group)
                .order_by("student__last_name", "student__first_name")
            )
            source_students = [membership.student for membership in memberships]
    elif lesson.student:
        individual_student = lesson.student

    try:
        from subscriptions.models import LessonAttendance
    except Exception:
        LessonAttendance = None

    attendance_by_student = {}
    if LessonAttendance:
        attendance_by_student = {
            item.student_id: item
            for item in LessonAttendance.objects.filter(schedule=lesson)
        }

    students = []
    if individual_student:
        source_students = [individual_student]

    for student in source_students:
        attendance = attendance_by_student.get(student.id)
        students.append({
            "id": student.id,
            "name": student.get_full_name() or student.username,
            "phone": student.phone or "",
            "attendance": None if not attendance else {
                "id": attendance.id,
                "status": attendance.status,
                "status_display": attendance.get_status_display(),
                "lessons_count": attendance.lessons_count,
                "lesson_deducted": attendance.lesson_deducted,
            },
        })

    return Response({
        "lesson": ScheduleSerializer(lesson).data,
        "students": students,
    })
