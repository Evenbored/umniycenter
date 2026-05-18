import json
import logging
from datetime import timedelta
from datetime import datetime
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from accounts.models import CustomUser, LeadSource, ParentProfile, StudentProfile, TeacherProfile, UserRole
from accounts.serializers import ParentListSerializer, ParentUpdateSerializer
from courses.models import Courses
from groups.models import SchoolGroups
from main.models import ParticipantRequest
from students.api_views import create_student_with_parent, generate_parent_username, validate_optional_email, validate_optional_phone, validate_source
from students.models import StudentGroups
from students.serializers import StudentUpdateSerializer
from subscriptions.models import Payment, Subscription, Tariff
from subscriptions.payment_service import PaymentService
from subscriptions.serializers import PaymentSerializer
from schedule.models import Schedule
from schedule.models import GroupScheduleTemplate
from communication.models import Message, Ticket, TicketStatus
from .api_views import build_dashboard_payload, parse_dashboard_date


logger = logging.getLogger(__name__)


def crm_toast(message, title="Готово", toast_type="success"):
    return {
        "type": toast_type,
        "title": title,
        "message": message,
    }


def hx_trigger(*events, toast=None):
    payload = {event: True for event in events}
    if toast:
        payload["crm:toast"] = toast
    return json.dumps(payload)


def render_oob_response(target_id, partial_template, context, request, drawer_html="", triggers=None):
    partial_html = render_to_string(partial_template, context, request=request)
    response = HttpResponse(
        f'<div id="{target_id}" hx-swap-oob="innerHTML">{partial_html}</div>{drawer_html}'
    )
    if triggers:
        response["HX-Trigger"] = triggers
    return response


def serializer_errors_to_text(errors):
    messages = []
    for value in errors.values():
        if isinstance(value, (list, tuple)):
            messages.append(" ".join(str(item) for item in value))
        else:
            messages.append(str(value))
    return " ".join(messages) or "Не удалось сохранить данные"


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.role != UserRole.ADMIN and not request.user.is_staff:
            return HttpResponseForbidden("CRM доступна только администратору")

        return view_func(request, *args, **kwargs)

    return wrapped


@login_required
@admin_required
def dashboard(request):
    selected_date = request.GET.get("date")
    dashboard = build_dashboard_payload(parse_dashboard_date(selected_date) if selected_date else None)
    context = {
        "dashboard": dashboard,
    }

    if request.headers.get("HX-Request") == "true":
        return render(request, "crm/partials/dashboard_content.html", context)

    return render(request, "crm/dashboard.html", context)


@login_required
@admin_required
def requests_view(request):
    return render(request, "crm/requests.html", get_requests_context(request))


@login_required
@admin_required
def students_view(request):
    return render(request, "crm/students.html", get_students_context(request))


@login_required
@admin_required
def courses_view(request):
    return render(request, "crm/courses.html", get_courses_context(request))


@login_required
@admin_required
def payments_view(request):
    return render(request, "crm/payments.html", get_payments_context(request))


@login_required
@admin_required
def subscriptions_view(request):
    return render(request, "crm/subscriptions.html", get_subscriptions_context(request))


@login_required
@admin_required
def groups_view(request):
    return render(request, "crm/groups.html", get_groups_context(request))


@login_required
@admin_required
def schedule_view(request):
    return render(request, "crm/schedule.html", get_schedule_context(request))


def get_schedule_queryset(request):
    lessons = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").order_by("classdateStart")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    group_id = request.GET.get("group")
    status_filter = request.GET.get("status")

    if date_from:
        lessons = lessons.filter(classdateStart__date__gte=date_from)
    if date_to:
        lessons = lessons.filter(classdateStart__date__lte=date_to)
    if group_id:
        lessons = lessons.filter(group_id=group_id)
    if status_filter:
        if status_filter in ["cancelled", "rescheduled"]:
            lessons = lessons.filter(status=status_filter)
        else:
            matching_ids = [lesson.id for lesson in lessons if lesson.actual_status == status_filter]
            lessons = lessons.filter(id__in=matching_ids)

    return list(lessons)


def prepare_schedule_lesson(lesson):
    labels = {
        "scheduled": "Запланировано",
        "completed": "Прошло",
        "cancelled": "Отменено",
        "rescheduled": "Перенесено",
    }
    lesson.actual_status_label = labels.get(lesson.actual_status, lesson.actual_status)
    return lesson


def get_schedule_context(request, selected_lesson=None, error=None):
    lessons = [prepare_schedule_lesson(lesson) for lesson in get_schedule_queryset(request)]
    if selected_lesson:
        selected_lesson = prepare_schedule_lesson(selected_lesson)
    return {
        "lessons": lessons,
        "schedule_templates": GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher").order_by("group__course__name", "group__number", "weekday", "start_time"),
        "groups": SchoolGroups.objects.select_related("course", "teacher").filter(is_active=True).order_by("course__name", "number"),
        "selected_lesson": selected_lesson,
        "form_error": error,
        "generate_form": {
            "date_from": request.POST.get("date_from") or request.GET.get("date_from") or "",
            "date_to": request.POST.get("date_to") or request.GET.get("date_to") or "",
            "group_id": request.POST.get("group_id") or request.GET.get("group_id") or "",
        },
    }


def get_schedule_template_context(request, selected_template=None, error=None):
    context = get_schedule_context(request)
    context.update({
        "selected_template": selected_template,
        "form_error": error,
        "template_form": {
            "group": str(getattr(selected_template, "group_id", request.POST.get("group") or request.GET.get("group") or "")),
            "weekday": str(getattr(selected_template, "weekday", request.POST.get("weekday") or 0)),
            "start_time": getattr(selected_template, "start_time", None) or request.POST.get("start_time") or "",
            "lessons_count": str(getattr(selected_template, "lessons_count", request.POST.get("lessons_count") or 2)),
            "is_active": getattr(selected_template, "is_active", True if request.method == "GET" else request.POST.get("is_active") in ["on", "true", "1"]),
        },
    })
    return context


def get_create_lesson_context(request, error=None):
    context = get_schedule_context(request)
    course_id = request.GET.get("course") or request.POST.get("course") or ""
    group_id = request.GET.get("group") or request.POST.get("group") or ""
    lesson_type = request.GET.get("lesson_type") or request.POST.get("lesson_type") or Schedule.LESSON_TYPE_REGULAR
    subscription_type = "group" if group_id else "individual"
    students = CustomUser.objects.filter(role=UserRole.STUDENT, is_active=True)
    if group_id:
        students = students.filter(studentgroups__group_id=group_id)
    if course_id:
        students = students.filter(
            subscriptions__status="active",
            subscriptions__tariff__course_id=course_id,
            subscriptions__tariff__subscription_type=subscription_type,
            subscriptions__end_date__gte=timezone.now().date(),
        )
    context.update({
        "form_error": error,
        "selected_course_id": str(course_id),
        "selected_group_id": str(group_id),
        "selected_lesson_type": lesson_type,
        "create_students": students.distinct().order_by("last_name", "first_name", "id"),
        "create_groups": context["groups"].filter(course_id=course_id) if course_id else SchoolGroups.objects.none(),
        "teachers": CustomUser.objects.filter(role=UserRole.TEACHER, is_active=True).order_by("last_name", "first_name", "id"),
        "courses": Courses.objects.all().order_by("name"),
    })
    return context


def get_lesson_attendance_context(request, lesson, error=None, success=None):
    try:
        from subscriptions.models import LessonAttendance
    except Exception:
        LessonAttendance = None

    if lesson.group:
        explicit_students = list(lesson.students.all().order_by("last_name", "first_name"))
        if explicit_students:
            students = explicit_students
        else:
            students = [membership.student for membership in StudentGroups.objects.select_related("student").filter(group=lesson.group).order_by("student__last_name", "student__first_name")]
    elif lesson.student:
        students = [lesson.student]
    else:
        students = []

    attendance_by_student = {}
    if LessonAttendance:
        attendance_by_student = {item.student_id: item for item in LessonAttendance.objects.filter(schedule=lesson)}

    attendance_rows = [{"student": student, "attendance": attendance_by_student.get(student.id)} for student in students]

    return {
        "selected_lesson": prepare_schedule_lesson(lesson),
        "attendance_students": students,
        "attendance_rows": attendance_rows,
        "attendance_by_student": attendance_by_student,
        "attendance_status_choices": LessonAttendance.ATTENDANCE_STATUS if LessonAttendance else [],
        "form_error": error,
        "form_success": success,
    }


@login_required
@admin_required
def schedule_today_view(request):
    return render(request, "crm/schedule_today.html", get_schedule_today_context(request))


def get_schedule_today_context(request, selected_lesson=None, selected_student=None, error=None, success=None):
    today = timezone.localdate()
    lessons = [
        prepare_schedule_lesson(lesson)
        for lesson in Schedule.objects.select_related("group", "group__course", "teacher", "student", "course")
        .filter(classdateStart__date=today)
        .order_by("classdateStart")
    ]
    if selected_lesson is None and lessons:
        selected_lesson = lessons[0]
    if selected_lesson:
        selected_lesson = prepare_schedule_lesson(selected_lesson)
    context = {
        "today": today,
        "today_lessons": lessons,
        "selected_lesson": selected_lesson,
        "selected_student": selected_student,
        "form_error": error,
        "form_success": success,
    }
    if selected_lesson:
        context.update(get_lesson_attendance_context(request, selected_lesson, error=error, success=success))
    return context


@login_required
@admin_required
def schedule_today_lessons_partial(request):
    return render(request, "crm/partials/schedule_today_lessons.html", get_schedule_today_context(request))


@login_required
@admin_required
def schedule_today_attendance_partial(request, lesson_id):
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "teacher", "student", "course"), id=lesson_id)
    return render(request, "crm/partials/schedule_today_attendance.html", get_schedule_today_context(request, selected_lesson=lesson))


@login_required
@admin_required
def schedule_today_student_partial(request, lesson_id, student_id):
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "teacher", "student", "course"), id=lesson_id)
    student = get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)
    return render(request, "crm/partials/schedule_today_student.html", get_schedule_today_context(request, selected_lesson=lesson, selected_student=student))


@login_required
@admin_required
def schedule_lessons_partial(request):
    return render(request, "crm/partials/schedule_lessons.html", get_schedule_context(request))


@login_required
@admin_required
def schedule_lesson_drawer_partial(request, lesson_id):
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "teacher", "student", "course"), id=lesson_id)
    context = {**get_schedule_context(request, selected_lesson=lesson), **get_lesson_attendance_context(request, lesson)}
    return render(request, "crm/partials/schedule_lesson_drawer.html", context)


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_lesson_cancel_partial(request, lesson_id):
    lesson = get_object_or_404(Schedule, id=lesson_id)
    lesson.status = "cancelled"
    lesson.cancel_reason = (request.POST.get("reason") or "").strip()
    lesson.save(update_fields=["status", "cancel_reason"])
    lesson = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").get(id=lesson.id)
    response = HttpResponse(
        render_to_string("crm/partials/schedule_lesson_drawer.html", {**get_schedule_context(request, selected_lesson=lesson), **get_lesson_attendance_context(request, lesson)}, request=request)
        + render_to_string("crm/partials/schedule_lessons.html", {**get_schedule_context(request), "lessons_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Занятие отменено"))
    return response


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_lesson_reschedule_partial(request, lesson_id):
    lesson = get_object_or_404(Schedule, id=lesson_id)
    try:
        new_start_raw = request.POST.get("classdateStart") or ""
        new_start = datetime.fromisoformat(new_start_raw)
        if timezone.is_naive(new_start):
            new_start = timezone.make_aware(new_start)
        lessons_count = int(request.POST.get("lessons_count") or 2)
        lesson_type = request.POST.get("lesson_type") or lesson.lesson_type
        if lessons_count not in (1, 2):
            raise ValueError("Занятие может длиться только 1 или 2 академических часа")
        if lesson_type not in dict(Schedule.LESSON_TYPE_CHOICES):
            raise ValueError("Выберите корректный тип занятия")
        if not lesson.original_classdateStart:
            lesson.original_classdateStart = lesson.classdateStart
            lesson.original_classdateEnd = lesson.classdateEnd
        from schedule.services import get_lesson_end_time
        lesson.classdateStart = new_start
        lesson.classdateEnd = get_lesson_end_time(new_start.time(), lessons_count)
        lesson.lesson_type = lesson_type
        lesson.is_single = lesson_type == Schedule.LESSON_TYPE_SINGLE
        lesson.status = "rescheduled"
        lesson.reschedule_reason = (request.POST.get("reason") or "").strip()
        lesson.save()
    except Exception as exc:
        lesson = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").get(id=lesson.id)
        return render(request, "crm/partials/schedule_lesson_drawer.html", {**get_schedule_context(request, selected_lesson=lesson, error=str(exc)), **get_lesson_attendance_context(request, lesson)}, status=400)

    lesson = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").get(id=lesson.id)
    response = HttpResponse(
        render_to_string("crm/partials/schedule_lesson_drawer.html", {**get_schedule_context(request, selected_lesson=lesson), **get_lesson_attendance_context(request, lesson)}, request=request)
        + render_to_string("crm/partials/schedule_lessons.html", {**get_schedule_context(request), "lessons_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Занятие перенесено"))
    return response


@login_required
@admin_required
def schedule_template_partial(request, template_id=None):
    template = None
    if template_id:
        template = get_object_or_404(GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher"), id=template_id)
    return render(request, "crm/partials/schedule_template_modal.html", get_schedule_template_context(request, selected_template=template))


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_template_save_partial(request, template_id=None):
    template = None
    if template_id:
        template = get_object_or_404(GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher"), id=template_id)
    try:
        group = get_object_or_404(SchoolGroups, id=request.POST.get("group")) if not template else template.group
        weekday = int(request.POST.get("weekday") or 0)
        start_time = request.POST.get("start_time") or ""
        lessons_count = int(request.POST.get("lessons_count") or 2)
        is_active = request.POST.get("is_active") in ["on", "true", "1"]
        if template is None:
            template = GroupScheduleTemplate.objects.create(group=group, weekday=weekday, start_time=start_time, lessons_count=lessons_count, is_active=is_active)
        else:
            template.group = group
            template.weekday = weekday
            template.start_time = start_time
            template.lessons_count = lessons_count
            template.is_active = is_active
            template.save()
    except Exception as exc:
        return render(request, "crm/partials/schedule_template_modal.html", get_schedule_template_context(request, selected_template=template, error=str(exc)), status=400)

    response = HttpResponse(
        render_to_string("crm/partials/schedule_templates.html", get_schedule_context(request), request=request)
        + render_to_string("crm/partials/schedule_template_modal.html", get_schedule_template_context(request, selected_template=template), request=request)
    )
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Стандартное время сохранено"))
    return response


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_template_delete_partial(request, template_id):
    template = get_object_or_404(GroupScheduleTemplate, id=template_id)
    template.delete()
    response = HttpResponse(render_to_string("crm/partials/schedule_templates.html", get_schedule_context(request), request=request))
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Стандартное время удалено"))
    return response


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_generate_partial(request):
    from django.utils.dateparse import parse_date
    from schedule.services import generate_schedule_for_range
    try:
        date_from = parse_date(request.POST.get("date_from") or "")
        date_to = parse_date(request.POST.get("date_to") or "")
        group_id = request.POST.get("group_id") or None
        if not date_from or not date_to:
            raise ValueError("Укажите период генерации")
        if date_to < date_from:
            raise ValueError("Дата окончания не может быть раньше даты начала")
        created = generate_schedule_for_range(date_from, date_to, group_id=group_id)

        context = get_schedule_context(request)
        response = HttpResponse(
            render_to_string("crm/partials/schedule_generate_drawer.html", {**context, "generate_success": f"Создано занятий: {len(created)}"}, request=request)
            + render_to_string("crm/partials/schedule_lessons.html", {**context, "lessons_oob": True}, request=request)
        )
        response["HX-Trigger"] = hx_trigger(toast=crm_toast(f"Создано занятий: {len(created)}"))
        return response
    except Exception as exc:
        return render(request, "crm/partials/schedule_generate_drawer.html", {**get_schedule_context(request), "form_error": str(exc)}, status=400)


@login_required
@admin_required
def schedule_create_lesson_drawer_partial(request):
    return render(request, "crm/partials/schedule_create_lesson_drawer.html", get_create_lesson_context(request))


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_lesson_create_partial(request):
    from schedule.services import get_lesson_end_time
    try:
        classdate_start = datetime.fromisoformat(request.POST.get("classdateStart") or "")
        if timezone.is_naive(classdate_start):
            classdate_start = timezone.make_aware(classdate_start)
        lessons_count = int(request.POST.get("lessons_count") or 2)
        lesson_type = request.POST.get("lesson_type") or Schedule.LESSON_TYPE_REGULAR
        teacher = get_object_or_404(CustomUser, id=request.POST.get("teacher"), role=UserRole.TEACHER)
        course = get_object_or_404(Courses, id=request.POST.get("course"))
        group_id = request.POST.get("group")
        student_id = request.POST.get("student")
        if not group_id and not student_id:
            raise ValueError("Выберите группу или ученика")
        lesson = Schedule.objects.create(
            lesson_type=lesson_type,
            classdateStart=classdate_start,
            classdateEnd=get_lesson_end_time(classdate_start.time(), lessons_count),
            teacher=teacher,
            course=course,
            status="scheduled",
            is_single=lesson_type == Schedule.LESSON_TYPE_SINGLE,
        )
        if group_id:
            lesson.group = get_object_or_404(SchoolGroups, id=group_id)
            lesson.course = lesson.group.course
            selected_student_ids = request.POST.getlist("students")
            lesson.save()
            if selected_student_ids:
                allowed_students = CustomUser.objects.filter(id__in=selected_student_ids, role=UserRole.STUDENT)
                lesson.students.set(allowed_students)
        else:
            lesson.student = get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)
            lesson.save()
        lesson.full_clean()
        lesson.save()
    except Exception as exc:
        return render(request, "crm/partials/schedule_create_lesson_drawer.html", get_create_lesson_context(request, error=str(exc)), status=400)

    response = HttpResponse(
        render_to_string("crm/partials/schedule_create_lesson_drawer.html", get_create_lesson_context(request), request=request)
        + render_to_string("crm/partials/schedule_lessons.html", {**get_schedule_context(request), "lessons_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Занятие создано"))
    return response


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_attendance_mark_partial(request, lesson_id, student_id):
    from subscriptions.models import LessonAttendance
    from subscriptions.services import SubscriptionService
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "student", "course"), id=lesson_id)
    student = get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)
    try:
        status_value = request.POST.get("status")
        lessons_count = int(request.POST.get("lessons_count") or 2)
        if LessonAttendance.objects.filter(schedule=lesson, student=student).exists():
            raise ValueError("Посещение уже отмечено для этого ученика")
        subscription = None
        lesson_deducted = False
        if status_value == "present" and not lesson.is_single:
            subscription, lessons_count = SubscriptionService.deduct_for_lesson(student, lesson, lessons_count, marked_by=request.user)
            lesson_deducted = True
        LessonAttendance.objects.create(schedule=lesson, student=student, status=status_value, lessons_count=lessons_count, subscription=subscription, lesson_deducted=lesson_deducted, marked_by=request.user)
        student.update_active_status()
    except Exception as exc:
        return render(request, "crm/partials/schedule_attendance.html", get_lesson_attendance_context(request, lesson, error=str(exc)), status=400)
    return render(request, "crm/partials/schedule_attendance.html", get_lesson_attendance_context(request, lesson, success="Посещение успешно отмечено"))


@login_required
@admin_required
@require_http_methods(["POST"])
def schedule_attendance_cancel_partial(request, attendance_id):
    from subscriptions.models import LessonAttendance
    from subscriptions.services import SubscriptionService
    attendance = get_object_or_404(LessonAttendance.objects.select_related("schedule", "subscription", "student"), id=attendance_id)
    lesson = attendance.schedule
    student = attendance.student
    if attendance.lesson_deducted and attendance.subscription:
        SubscriptionService.refund_for_attendance(attendance, created_by=request.user)
    attendance.delete()
    student.update_active_status()
    return render(request, "crm/partials/schedule_attendance.html", get_lesson_attendance_context(request, lesson, success="Отметка отменена"))


@login_required
@admin_required
def teachers_view(request):
    return render(request, "crm/teachers.html", get_teachers_context(request))


@login_required
@admin_required
def messages_view(request):
    return render(request, "crm/messages.html", get_messages_context(request))


@login_required
@admin_required
def parents_view(request):
    return render(request, "crm/parents.html", get_parents_context(request))


def get_parents_queryset(request):
    parents = CustomUser.objects.filter(role=UserRole.PARENT).prefetch_related(
        "parent_profile__students",
        "parent_profile__students__user",
    )
    search = (request.GET.get("search") or "").strip()
    sort = request.GET.get("sort") or "name_az"

    if search:
        parents = parents.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(parent_profile__students__user__first_name__icontains=search)
            | Q(parent_profile__students__user__last_name__icontains=search)
        ).distinct()

    parents = parents.order_by("last_name", "first_name", "id")
    if sort == "name_za":
        parents = parents.order_by("-last_name", "-first_name", "id")

    return parents


def get_parents_context(request):
    parents = get_parents_queryset(request)
    parents_data = ParentListSerializer(parents, many=True).data
    sort = request.GET.get("sort") or "name_az"
    if sort == "children_many":
        parents_data = sorted(parents_data, key=lambda item: len(item.get("children") or []), reverse=True)
    return {
        "parents": parents_data,
        "parents_count": len(parents_data),
        "sort": sort,
    }


def get_student_membership_prefetch():
    from django.db.models import Prefetch
    return Prefetch(
        "studentgroups_set",
        queryset=StudentGroups.objects.select_related("group", "group__course", "group__teacher").order_by("group__course__name", "group__number"),
        to_attr="student_group_memberships",
    )


def get_students_queryset(request):
    students = CustomUser.objects.filter(role=UserRole.STUDENT).prefetch_related(
        get_student_membership_prefetch(),
        "student_profile__parents__user",
        "subscriptions__tariff__course",
    )
    search = (request.GET.get("search") or "").strip()
    course = request.GET.get("course") or ""
    group = request.GET.get("group") or ""
    status = request.GET.get("status") or "active"
    without_group = request.GET.get("without_group") in ["on", "true", "1"]
    sort = request.GET.get("sort") or "name_az"

    if search:
        students = students.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(city__icontains=search)
            | Q(studentgroups__group__number__icontains=search)
            | Q(studentgroups__group__course__name__icontains=search)
        ).distinct()

    if course:
        students = students.filter(studentgroups__group__course_id=course).distinct()
    if group:
        students = students.filter(studentgroups__group_id=group).distinct()
    if without_group:
        students = students.filter(studentgroups__isnull=True)

    if status == "active":
        students = students.filter(is_active=True)
    elif status == "archive":
        students = students.filter(is_active=False)

    ordering_map = {
        "name_za": ("-last_name", "-first_name", "id"),
        "date_new": ("-date_joined", "id"),
        "date_old": ("date_joined", "id"),
    }
    return students.order_by(*ordering_map.get(sort, ("last_name", "first_name", "id")))


def get_student_for_drawer(student_id):
    return get_object_or_404(
        CustomUser.objects.prefetch_related(
            get_student_membership_prefetch(),
            "student_profile__parents__user",
            "subscriptions__tariff__course",
            "subscriptions__group",
            "subscriptions__logs",
        ),
        id=student_id,
        role=UserRole.STUDENT,
    )


def get_students_context(request, selected_student=None, error=None):
    students = get_students_queryset(request)
    return {
        "students": students,
        "students_count": students.count(),
        "groups": SchoolGroups.objects.select_related("course", "teacher").order_by("course__name", "number"),
        "courses": Courses.objects.all().order_by("name"),
        "source_choices": LeadSource.choices,
        "selected_student": selected_student,
        "form_error": error,
    }


def get_student_parents(student):
    try:
        return [profile.user for profile in student.student_profile.parents.select_related("user").all()]
    except StudentProfile.DoesNotExist:
        return []


def get_student_subscriptions(student):
    return student.subscriptions.select_related("tariff", "tariff__course", "group").prefetch_related("logs").order_by("-created_at")


def build_student_form_values(student=None, data=None):
    data = data or {}

    def val(name, default=""):
        value = data.get(name)
        if value not in [None, ""]:
            return value
        return default

    if student:
        source = ""
        try:
            source = student.student_profile.source or ""
        except StudentProfile.DoesNotExist:
            pass
        return {
            "last_name": val("last_name", student.last_name),
            "first_name": val("first_name", student.first_name),
            "username": val("username", student.username),
            "phone": val("phone", student.phone or ""),
            "email": val("email", student.email or ""),
            "city": val("city", student.city or ""),
            "country": val("country", student.country or ""),
            "sex": str(int(bool(student.sex))) if data.get("sex") in [None, ""] else data.get("sex"),
            "is_active": student.is_active if data.get("is_active") in [None, ""] else data.get("is_active") == "true",
            "source": val("source", source),
        }

    return {
        "last_name": val("last_name"),
        "first_name": val("first_name"),
        "username": val("username"),
        "password": val("password", "student123"),
        "phone": val("phone"),
        "email": val("email"),
        "city": val("city"),
        "country": val("country", "Россия"),
        "sex": val("sex"),
        "source": val("source"),
        "parent_last_name": val("parent_last_name"),
        "parent_first_name": val("parent_first_name"),
        "parent_phone": val("parent_phone"),
        "parent_email": val("parent_email"),
    }


def build_student_drawer_context(request, student=None, data=None, error=None):
    return {
        **get_students_context(request, selected_student=student, error=error),
        "student_form": build_student_form_values(student=student, data=data),
        "student_parents": get_student_parents(student) if student else [],
        "student_subscriptions": get_student_subscriptions(student) if student else [],
        "student_payments": get_student_payments(student) if student else [],
        "available_groups": SchoolGroups.objects.select_related("course", "teacher").filter(is_active=True).order_by("course__name", "number"),
    }


def get_teachers_queryset(request):
    teachers = CustomUser.objects.filter(role=UserRole.TEACHER).prefetch_related("schoolgroups_set__course")
    search = (request.GET.get("search") or "").strip()
    status = request.GET.get("status") or "active"
    sort = request.GET.get("sort") or "name_az"

    if search:
        teachers = teachers.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        ).distinct()
    if status == "active":
        teachers = teachers.filter(is_active=True)
    elif status == "archive":
        teachers = teachers.filter(is_active=False)

    ordering_map = {
        "name_za": ("-last_name", "-first_name", "id"),
        "date_new": ("-date_joined", "id"),
        "date_old": ("date_joined", "id"),
    }
    return teachers.order_by(*ordering_map.get(sort, ("last_name", "first_name", "id")))


def get_teacher_for_drawer(teacher_id):
    return get_object_or_404(CustomUser.objects.prefetch_related("schoolgroups_set__course"), id=teacher_id, role=UserRole.TEACHER)


def get_teacher_schedule(teacher):
    from django.utils import timezone
    return Schedule.objects.filter(teacher=teacher, classdateStart__gte=timezone.now()).select_related("group", "group__course", "course").order_by("classdateStart")[:10]


def get_teachers_context(request, selected_teacher=None, error=None):
    teachers = get_teachers_queryset(request)
    return {
        "teachers": teachers,
        "teachers_count": teachers.count(),
        "selected_teacher": selected_teacher,
        "teacher_groups": selected_teacher.schoolgroups_set.select_related("course").all() if selected_teacher else [],
        "teacher_schedule": get_teacher_schedule(selected_teacher) if selected_teacher else [],
        "teacher_form": build_teacher_form_values(selected_teacher, request.POST if request.method == "POST" else None),
        "form_error": error,
    }


def build_teacher_form_values(teacher=None, data=None):
    data = data or {}
    def val(name, default=""):
        value = data.get(name)
        if value not in [None, ""]:
            return value
        return default
    if teacher:
        return {
            "last_name": val("last_name", teacher.last_name),
            "first_name": val("first_name", teacher.first_name),
            "username": val("username", teacher.username),
            "phone": val("phone", teacher.phone or ""),
            "email": val("email", teacher.email or ""),
            "city": val("city", teacher.city or ""),
            "country": val("country", teacher.country or ""),
            "sex": str(int(bool(teacher.sex))) if data.get("sex") in [None, ""] else data.get("sex"),
            "is_active": teacher.is_active if data.get("is_active") in [None, ""] else data.get("is_active") == "true",
        }
    return {
        "last_name": val("last_name"),
        "first_name": val("first_name"),
        "username": val("username"),
        "password": val("password", "teacher123"),
        "phone": val("phone"),
        "email": val("email"),
        "city": val("city"),
        "country": val("country", "Россия"),
        "sex": val("sex"),
        "is_active": True,
    }


def validate_teacher_payload(data, teacher=None, creating=False):
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    import re
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    if not first_name or not last_name or not username or (creating and not password):
        raise ValueError("Заполните все обязательные поля")
    if phone and not re.match(r"^\+7\d{10}$", phone):
        raise ValueError("Телефон должен быть в формате +7XXXXXXXXXX")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("Введите корректный email")
    users = CustomUser.objects.all()
    if teacher:
        users = users.exclude(id=teacher.id)
    if users.filter(username=username).exists():
        raise ValueError("Пользователь с таким логином уже существует")
    if email and users.filter(email=email).exists():
        raise ValueError("Пользователь с таким email уже существует")
    if phone and users.filter(phone=phone).exists():
        raise ValueError("Пользователь с таким номером телефона уже существует")
    return {
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "password": password,
        "phone": phone or None,
        "email": email or None,
        "city": (data.get("city") or "").strip() or None,
        "country": (data.get("country") or "").strip() or None,
        "sex": str(data.get("sex")) == "1" or data.get("sex") is True,
        "is_active": data.get("is_active", "true") == "true",
    }


def get_groups_queryset(request):
    from django.db.models import Count
    groups = SchoolGroups.objects.select_related("course", "teacher").annotate(students_count=Count("studentgroups", distinct=True))
    search = (request.GET.get("search") or "").strip()
    course = request.GET.get("course") or ""
    teacher = request.GET.get("teacher") or ""
    status = request.GET.get("status") or "active"
    sort = request.GET.get("sort") or "name_az"
    empty = request.GET.get("empty") in ["on", "true", "1"]

    if search:
        groups = groups.filter(Q(number__icontains=search) | Q(course__name__icontains=search) | Q(teacher__first_name__icontains=search) | Q(teacher__last_name__icontains=search)).distinct()
    if course:
        groups = groups.filter(course_id=course)
    if teacher:
        groups = groups.filter(teacher_id=teacher)
    if status == "active":
        groups = groups.filter(is_active=True)
    elif status == "archive":
        groups = groups.filter(is_active=False)
    if empty:
        groups = groups.filter(students_count=0)

    ordering_map = {
        "students_desc": ("-students_count", "course__name", "number"),
        "students_asc": ("students_count", "course__name", "number"),
    }
    return groups.order_by(*ordering_map.get(sort, ("course__name", "number")))


def get_group_for_drawer(group_id):
    from django.db.models import Count
    return get_object_or_404(SchoolGroups.objects.select_related("course", "teacher").annotate(students_count=Count("studentgroups", distinct=True)), id=group_id)


def get_group_students(group):
    return CustomUser.objects.filter(studentgroups__group=group, role=UserRole.STUDENT).order_by("last_name", "first_name").distinct()


def get_groups_context(request, selected_group=None, error=None, data=None):
    return {
        "groups": get_groups_queryset(request),
        "groups_count": get_groups_queryset(request).count(),
        "courses": Courses.objects.all().order_by("name"),
        "teachers": CustomUser.objects.filter(role=UserRole.TEACHER, is_active=True).order_by("last_name", "first_name", "id"),
        "selected_group": selected_group,
        "group_students": get_group_students(selected_group) if selected_group else [],
        "schedule_templates": selected_group.schedule_templates.all().order_by("weekday", "start_time") if selected_group else [],
        "group_form": build_group_form_values(selected_group, data),
        "form_error": error,
    }


def build_group_form_values(group=None, data=None):
    data = data or {}
    def val(name, default=""):
        value = data.get(name)
        if value not in [None, ""]:
            return value
        return default
    if group:
        return {
            "number": val("number", group.number),
            "course": str(val("course", group.course_id)),
            "teacher": str(val("teacher", group.teacher_id)),
            "is_active": group.is_active if data.get("is_active") in [None, ""] else data.get("is_active") == "true",
        }
    return {"number": val("number"), "course": str(val("course")), "teacher": str(val("teacher")), "is_active": True, "default_lesson_time": val("default_lesson_time"), "default_lesson_duration": val("default_lesson_duration", "90")}


def save_group_from_post(request, group=None):
    number = (request.POST.get("number") or "").strip()
    course = Courses.objects.filter(id=request.POST.get("course")).first()
    teacher = CustomUser.objects.filter(id=request.POST.get("teacher"), role=UserRole.TEACHER).first()
    if not number or not course or not teacher:
        raise ValueError("Заполните номер группы, курс и преподавателя")
    duplicate = SchoolGroups.objects.filter(number__iexact=number)
    if group:
        duplicate = duplicate.exclude(id=group.id)
    if duplicate.exists():
        raise ValueError("Группа с таким номером уже существует")
    if group is None:
        group = SchoolGroups.objects.create(number=number, course=course, teacher=teacher, is_active=True)
    else:
        group.number = number
        group.course = course
        group.teacher = teacher
        group.is_active = request.POST.get("is_active", "true") == "true"
        group.save()
    return group


def get_tickets_queryset(request):
    tickets = Ticket.objects.select_related("parent", "assigned_admin").prefetch_related("messages", "messages__sender")
    search = (request.GET.get("search") or "").strip()
    status = request.GET.get("status") or "all"
    period = request.GET.get("period") or "all"
    if search:
        tickets = tickets.filter(Q(parent__first_name__icontains=search) | Q(parent__last_name__icontains=search) | Q(parent__phone__icontains=search) | Q(subject__icontains=search)).distinct()
    if status != "all":
        tickets = tickets.filter(status=status)
    if period != "all":
        from django.utils import timezone
        today = timezone.localdate()
        if period == "today":
            tickets = tickets.filter(created_at__date=today)
        elif period == "week":
            tickets = tickets.filter(created_at__date__gte=today - timedelta(days=7))
        elif period == "month":
            tickets = tickets.filter(created_at__date__gte=today - timedelta(days=30))
    return tickets.order_by("-last_message_at", "-created_at")


def get_messages_context(request, selected_ticket=None, error=None):
    tickets = get_tickets_queryset(request)
    all_tickets = Ticket.objects.all()
    selected_ticket_id = request.GET.get("selected_ticket_id")
    if selected_ticket is None and selected_ticket_id:
        selected_ticket = Ticket.objects.select_related("parent", "assigned_admin").prefetch_related("messages", "messages__sender").filter(id=selected_ticket_id).first()
    return {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "status": request.GET.get("status") or "all",
        "period": request.GET.get("period") or "all",
        "search": (request.GET.get("search") or "").strip(),
        "all_count": all_tickets.count(),
        "open_count": all_tickets.filter(status=TicketStatus.OPEN).count(),
        "in_progress_count": all_tickets.filter(status=TicketStatus.IN_PROGRESS).count(),
        "closed_count": all_tickets.filter(status=TicketStatus.CLOSED).count(),
        "form_error": error,
    }


def get_student_payments(student):
    return Payment.objects.filter(subscription__student=student).select_related(
        "parent", "subscription", "subscription__tariff", "subscription__tariff__course"
    ).order_by("-created_at")


def build_buy_tariff_context(request, student, data=None, error=None):
    data = data or request.GET
    course_id = data.get("course") or data.get("course_id") or ""
    tariff_id = data.get("tariff_id") or ""
    selected_tariff = Tariff.objects.select_related("course").filter(id=tariff_id).first() if tariff_id else None
    if selected_tariff and not course_id:
        course_id = selected_tariff.course_id
    tariffs = Tariff.objects.select_related("course").filter(is_active=True)
    groups = SchoolGroups.objects.select_related("course", "teacher").filter(is_active=True)
    if course_id:
        tariffs = tariffs.filter(course_id=course_id)
        groups = groups.filter(course_id=course_id)

    return {
        "selected_student": student,
        "courses": Courses.objects.all().order_by("name"),
        "tariffs": tariffs.order_by("course__name", "lessons_count", "name"),
        "groups": groups.order_by("course__name", "number"),
        "selected_course_id": str(course_id),
        "selected_tariff_id": str(tariff_id),
        "selected_tariff": selected_tariff,
        "payment_method": data.get("payment_method") or "online",
        "group_id": str(data.get("group_id") or ""),
        "add_to_group": data.get("add_to_group") in ["on", "true", "1"],
        "form_error": error,
    }


def get_payments_queryset(request):
    payments = Payment.objects.select_related(
        "parent",
        "subscription",
        "subscription__student",
        "subscription__tariff",
        "subscription__tariff__course",
    )
    search = (request.GET.get("search") or "").strip()
    status = request.GET.get("status") or ""
    method = request.GET.get("method") or ""
    sort = request.GET.get("sort") or "date_new"

    if search:
        payments = payments.filter(
            Q(parent__first_name__icontains=search)
            | Q(parent__last_name__icontains=search)
            | Q(parent__phone__icontains=search)
            | Q(parent__email__icontains=search)
            | Q(subscription__student__first_name__icontains=search)
            | Q(subscription__student__last_name__icontains=search)
            | Q(subscription__tariff__name__icontains=search)
            | Q(subscription__tariff__course__name__icontains=search)
            | Q(transaction_id__icontains=search)
            | Q(yookassa_payment_id__icontains=search)
        )
    if status:
        payments = payments.filter(status=status)
    if method:
        payments = payments.filter(payment_method=method)

    if sort == "date_old":
        payments = payments.order_by("created_at")
    elif sort == "amount_desc":
        payments = payments.order_by("-amount", "-created_at")
    elif sort == "amount_asc":
        payments = payments.order_by("amount", "-created_at")
    else:
        payments = payments.order_by("-created_at")

    return payments


def get_payments_context(request, payment=None):
    payments = get_payments_queryset(request)
    payments_data = PaymentSerializer(payments, many=True).data
    completed_amount = sum(float(item.get("amount") or 0) for item in payments_data if item.get("status") == "completed")
    pending_count = sum(1 for item in payments_data if item.get("status") == "pending")
    problem_count = sum(1 for item in payments_data if item.get("status") in ["failed", "canceled", "refunded"])

    return {
        "payments": payments_data,
        "payments_count": len(payments_data),
        "completed_amount": completed_amount,
        "pending_count": pending_count,
        "problem_count": problem_count,
        "selected_payment": PaymentSerializer(payment).data if payment else None,
    }


def get_subscriptions_queryset(request):
    subscriptions = Subscription.objects.select_related(
        "student",
        "parent",
        "tariff",
        "tariff__course",
        "group",
    ).prefetch_related("payments", "logs")

    search = (request.GET.get("search") or "").strip()
    status_filter = request.GET.get("status") or ""
    subscription_type = request.GET.get("subscription_type") or ""
    course_id = request.GET.get("course") or ""
    risk = request.GET.get("risk") or ""
    sort = request.GET.get("sort") or "date_new"
    today = timezone.now().date()

    if search:
        subscriptions = subscriptions.filter(
            Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
            | Q(student__username__icontains=search)
            | Q(parent__first_name__icontains=search)
            | Q(parent__last_name__icontains=search)
            | Q(parent__phone__icontains=search)
            | Q(parent__email__icontains=search)
            | Q(tariff__name__icontains=search)
            | Q(tariff__course__name__icontains=search)
            | Q(group__number__icontains=search)
        )
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)
    if subscription_type:
        subscriptions = subscriptions.filter(tariff__subscription_type=subscription_type)
    if course_id:
        subscriptions = subscriptions.filter(tariff__course_id=course_id)

    if risk == "ending_lessons":
        subscriptions = subscriptions.filter(status="active", lessons_used__gte=F("lessons_total") - 2)
    elif risk == "ending_date":
        subscriptions = subscriptions.filter(status="active", end_date__gte=today, end_date__lte=today + timedelta(days=7))
    elif risk == "expired_date":
        subscriptions = subscriptions.filter(end_date__lt=today).exclude(status__in=["canceled", "frozen"])
    elif risk == "pending_payment":
        subscriptions = subscriptions.filter(status="pending")
    elif risk == "negative":
        subscriptions = subscriptions.filter(lessons_used__gt=F("lessons_total"))

    if sort == "date_old":
        subscriptions = subscriptions.order_by("created_at")
    elif sort == "end_soon":
        subscriptions = subscriptions.order_by("end_date", "lessons_total", "-created_at")
    elif sort == "lessons_low":
        subscriptions = subscriptions.order_by("lessons_total", "-lessons_used", "end_date")
    elif sort == "student_az":
        subscriptions = subscriptions.order_by("student__last_name", "student__first_name", "-created_at")
    else:
        subscriptions = subscriptions.order_by("-created_at")

    return subscriptions.distinct()


def prepare_subscription_for_crm(subscription):
    today = timezone.now().date()
    lessons_remaining = subscription.lessons_remaining
    total = subscription.lessons_total or 0
    used = subscription.lessons_used or 0
    subscription.lessons_percent = min(max(round((used / total) * 100), 0), 100) if total else 0
    subscription.days_remaining = (subscription.end_date - today).days if subscription.end_date else None
    subscription.total_paid = subscription.payments.filter(status="completed").aggregate(total=Sum("amount"))["total"] or 0
    subscription.pending_payments_count = subscription.payments.filter(status="pending").count()
    subscription.last_payment = subscription.payments.order_by("-created_at").first()

    risk_labels = []
    if subscription.status == "pending":
        risk_labels.append("Ожидает оплаты")
    if subscription.status == "active" and lessons_remaining <= 2:
        risk_labels.append("Мало занятий")
    if subscription.status == "active" and subscription.end_date and 0 <= subscription.days_remaining <= 7:
        risk_labels.append("Скоро истекает")
    if subscription.end_date and subscription.end_date < today and subscription.status not in ["canceled", "frozen"]:
        risk_labels.append("Срок истек")
    if lessons_remaining < 0:
        risk_labels.append("В минусе")
    if subscription.is_frozen:
        risk_labels.append("Заморожен")
    subscription.risk_labels = risk_labels

    if subscription.is_frozen:
        subscription.crm_status_label = "Заморожен"
        subscription.crm_status_class = "archive"
    elif subscription.status == "active" and subscription.is_valid:
        subscription.crm_status_label = "Активен"
        subscription.crm_status_class = "active"
    elif subscription.status == "pending":
        subscription.crm_status_label = "Ожидает оплаты"
        subscription.crm_status_class = "archive"
    else:
        subscription.crm_status_label = subscription.get_status_display()
        subscription.crm_status_class = "archive"
    return subscription


def get_subscriptions_context(request, subscription=None, error=None):
    subscriptions = [prepare_subscription_for_crm(item) for item in get_subscriptions_queryset(request)]
    all_subscriptions = Subscription.objects.all()
    today = timezone.now().date()

    return {
        "subscriptions": subscriptions,
        "subscriptions_count": len(subscriptions),
        "active_count": all_subscriptions.filter(status="active", end_date__gte=today).count(),
        "pending_count": all_subscriptions.filter(status="pending").count(),
        "ending_lessons_count": all_subscriptions.filter(status="active", lessons_used__gte=F("lessons_total") - 2).count(),
        "ending_date_count": all_subscriptions.filter(status="active", end_date__gte=today, end_date__lte=today + timedelta(days=7)).count(),
        "expired_count": all_subscriptions.filter(end_date__lt=today).exclude(status__in=["canceled", "frozen"]).count(),
        "courses": Courses.objects.all().order_by("name"),
        "status_choices": Subscription.STATUS_CHOICES,
        "subscription_type_choices": Tariff.SUBSCRIPTION_TYPE_CHOICES,
        "selected_subscription": prepare_subscription_for_crm(subscription) if subscription else None,
        "subscription_logs": subscription.logs.select_related("created_by", "related_lesson").order_by("-created_at")[:20] if subscription else [],
        "subscription_payments": subscription.payments.select_related("parent").order_by("-created_at") if subscription else [],
        "form_error": error,
    }


def get_subscription_for_drawer(subscription_id):
    return get_object_or_404(
        Subscription.objects.select_related(
            "student",
            "parent",
            "tariff",
            "tariff__course",
            "group",
        ).prefetch_related("payments", "logs"),
        id=subscription_id,
    )


def get_payment_for_drawer(payment_id):
    return get_object_or_404(
        Payment.objects.select_related(
            "parent",
            "subscription",
            "subscription__student",
            "subscription__tariff",
            "subscription__tariff__course",
        ),
        id=payment_id,
    )


def normalize_serialized_payment_dates(payment_data):
    info = payment_data.get("subscription_info") or {}
    for key in ["start_date", "end_date"]:
        value = info.get(key)
        if value and hasattr(value, "strftime"):
            info[key] = value.strftime("%d.%m.%Y")
    return payment_data


def build_payment_drawer_context(request, payment=None, error=None):
    selected_payment = None
    if payment:
        selected_payment = normalize_serialized_payment_dates(PaymentSerializer(payment).data)

    return {
        **get_payments_context(request),
        "selected_payment": selected_payment,
        "form_error": error,
    }


def get_requests_queryset(request):
    requests = ParticipantRequest.objects.prefetch_related("courses")
    search = (request.GET.get("search") or "").strip()
    status = request.GET.get("status") or "new"
    sort = request.GET.get("sort") or "-created"

    if search:
        requests = requests.filter(
            Q(parent_fio__icontains=search)
            | Q(child_fio__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(courses__name__icontains=search)
        ).distinct()
    if status == "new":
        requests = requests.filter(checked=False)
    elif status == "processed":
        requests = requests.filter(checked=True)

    if sort == "created":
        requests = requests.order_by("created")
    elif sort == "child_fio":
        requests = requests.order_by("child_fio", "-created")
    else:
        requests = requests.order_by("-created")

    return requests


def get_requests_context(request, selected_request=None, error=None):
    requests = get_requests_queryset(request)
    return {
        "participant_requests": requests,
        "requests_count": requests.count(),
        "selected_request": selected_request,
        "form_error": error,
    }


def build_request_drawer_context(request, participant_request=None, error=None):
    return {
        **get_requests_context(request, selected_request=participant_request, error=error),
    }


def build_student_from_request_context(request, participant_request=None, data=None, error=None):
    data = data or {}
    child_name = split_name(participant_request.child_fio if participant_request else "")
    parent_name = split_name(participant_request.parent_fio if participant_request else "")

    def value(name, default=""):
        return data.get(name, default)

    form = {
        "last_name": value("last_name", child_name["last_name"]),
        "first_name": value("first_name", child_name["first_name"]),
        "birth_date": value("birth_date", ""),
        "sex": value("sex", ""),
        "phone": value("phone", ""),
        "email": value("email", ""),
        "city": value("city", ""),
        "country": value("country", "Россия"),
        "source": value("source", participant_request.source if participant_request else ""),
        "parent_last_name": value("parent_last_name", parent_name["last_name"]),
        "parent_first_name": value("parent_first_name", parent_name["first_name"]),
        "parent_phone": value("parent_phone", participant_request.phone if participant_request else ""),
        "parent_email": value("parent_email", participant_request.email if participant_request else ""),
        "username": value("username", make_username(participant_request.child_fio if participant_request else "student")),
        "password": value("password", f"student{participant_request.id}" if participant_request else "student123"),
    }

    return {
        "participant_request": participant_request,
        "student_form": form,
        "source_choices": LeadSource.choices,
        "form_error": error,
    }


def get_request_for_drawer(request_id):
    return get_object_or_404(ParticipantRequest.objects.prefetch_related("courses"), id=request_id)


def split_name(value):
    parts = [part for part in str(value or "").strip().split() if part]
    return {
        "last_name": parts[0] if parts else "",
        "first_name": parts[1] if len(parts) > 1 else "",
    }


def make_username(value, fallback="student"):
    import re
    base = re.sub(r"[^a-zа-яё0-9]+", "_", str(value or "").strip().lower()).strip("_") or fallback
    username = base[:140]
    counter = 1
    while CustomUser.objects.filter(username=username).exists():
        suffix = f"_{counter}"
        username = f"{base[:150 - len(suffix)]}{suffix}"
        counter += 1
    return username


@login_required
@admin_required
def students_table_partial(request):
    return render(request, "crm/partials/students_table.html", get_students_context(request))


@login_required
@admin_required
def student_drawer_partial(request, student_id=None):
    student = get_student_for_drawer(student_id) if student_id else None
    return render(request, "crm/partials/student_drawer.html", build_student_drawer_context(request, student=student))


def update_student_from_post(request, student):
    serializer = StudentUpdateSerializer(student, data=request.POST, partial=True)
    if not serializer.is_valid():
        raise ValueError(serializer_errors_to_text(serializer.errors))

    parents_data = []
    parent_ids = request.POST.getlist("parent_id")
    parent_first_names = request.POST.getlist("parent_first_name")
    parent_last_names = request.POST.getlist("parent_last_name")
    parent_phones = request.POST.getlist("parent_phone")
    parent_emails = request.POST.getlist("parent_email")
    for index, first_name in enumerate(parent_first_names):
        if not first_name and not parent_last_names[index] and not parent_phones[index] and not parent_emails[index]:
            continue
        parents_data.append({
            "id": int(parent_ids[index]) if parent_ids[index] else None,
            "first_name": first_name,
            "last_name": parent_last_names[index],
            "phone": parent_phones[index] or None,
            "email": parent_emails[index] or None,
        })

    source, source_error = validate_source(request.POST.get("source"))
    if source_error:
        raise ValueError(source_error)
    if len(parents_data) > 2:
        raise ValueError("У ученика может быть не больше двух родителей")

    with transaction.atomic():
        serializer.save()
        student_profile, _ = StudentProfile.objects.get_or_create(user=student)
        student_profile.source = source
        student_profile.save(update_fields=["source"])

        if parents_data:
            current_parent_profile_ids = set(student_profile.parents.values_list("id", flat=True))
            target_profiles = []
            for parent_data in parents_data:
                parent_id = parent_data.get("id")
                parent_first_name = (parent_data.get("first_name") or "").strip()
                parent_last_name = (parent_data.get("last_name") or "").strip()
                parent_phone, phone_error = validate_optional_phone(parent_data.get("phone"))
                parent_email, email_error = validate_optional_email(parent_data.get("email"))
                if not parent_first_name or not parent_last_name:
                    raise ValueError("Заполните имя и фамилию родителя")
                if phone_error:
                    raise ValueError(phone_error)
                if email_error:
                    raise ValueError(email_error)

                if parent_id:
                    parent_user = CustomUser.objects.get(id=parent_id, role=UserRole.PARENT)
                    parent_profile = parent_user.parent_profile
                    if parent_profile.id not in current_parent_profile_ids:
                        raise ValueError("Родитель не привязан к этому ученику")
                elif parent_phone:
                    parent_user = CustomUser.objects.filter(phone=parent_phone, role=UserRole.PARENT).first()
                    if parent_user:
                        parent_profile, _ = ParentProfile.objects.get_or_create(user=parent_user)
                    else:
                        parent_user = CustomUser.objects.create_user(
                            phone=parent_phone,
                            username=generate_parent_username(parent_first_name, parent_last_name, parent_phone),
                            first_name=parent_first_name,
                            last_name=parent_last_name,
                            email=parent_email,
                            role=UserRole.PARENT,
                            password=request.POST.get("parent_password") or "parent123",
                            sex=False,
                        )
                        parent_profile = ParentProfile.objects.create(user=parent_user)
                else:
                    if parent_email and CustomUser.objects.filter(email=parent_email).exists():
                        raise ValueError("Пользователь с таким email родителя уже существует")
                    parent_user = CustomUser.objects.create_user(
                        phone=None,
                        username=generate_parent_username(parent_first_name, parent_last_name),
                        first_name=parent_first_name,
                        last_name=parent_last_name,
                        email=parent_email,
                        role=UserRole.PARENT,
                        password=request.POST.get("parent_password") or "parent123",
                        sex=False,
                    )
                    parent_profile = ParentProfile.objects.create(user=parent_user)

                if parent_phone and parent_user.phone != parent_phone:
                    if CustomUser.objects.filter(phone=parent_phone).exclude(pk=parent_user.pk).exists():
                        raise ValueError("Пользователь с таким телефоном родителя уже существует")
                    parent_user.phone = parent_phone
                elif not parent_phone:
                    parent_user.phone = None
                if parent_email != parent_user.email:
                    if parent_email and CustomUser.objects.filter(email=parent_email).exclude(pk=parent_user.pk).exists():
                        raise ValueError("Пользователь с таким email родителя уже существует")
                    parent_user.email = parent_email
                parent_user.first_name = parent_first_name
                parent_user.last_name = parent_last_name
                parent_user.save()
                if parent_profile not in target_profiles:
                    target_profiles.append(parent_profile)

            for profile in target_profiles:
                profile.students.add(student_profile)


@login_required
@admin_required
@require_http_methods(["POST"])
def student_save_partial(request, student_id=None):
    student = get_student_for_drawer(student_id) if student_id else None
    try:
        if student is None:
            result, error = create_student_with_parent(request.POST)
            if error:
                raise ValueError(error.get("error") or serializer_errors_to_text(error))
            student = result["student"]
        else:
            update_student_from_post(request, student)
    except Exception as exc:
        return render(
            request,
            "crm/partials/student_drawer.html",
            build_student_drawer_context(request, student=student, data=request.POST, error=str(exc)),
            status=400,
        )

    student = get_student_for_drawer(student.id)
    drawer_html = render_to_string("crm/partials/student_drawer.html", build_student_drawer_context(request, student=student), request=request)
    return render_oob_response(
        "studentsTableHost",
        "crm/partials/students_table.html",
        get_students_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Данные ученика сохранены")),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def student_add_group_partial(request, student_id):
    from subscriptions.models import Subscription, Tariff, SubscriptionLog
    student = get_student_for_drawer(student_id)
    group_id = request.POST.get("group_id")
    force_add = request.POST.get("force_add") == "on"
    try:
        if not group_id:
            raise ValueError("Выберите группу")
        group = SchoolGroups.objects.get(id=group_id)
        subscription = Subscription.objects.filter(
            student=student,
            status="active",
            tariff__course=group.course,
            tariff__subscription_type=Tariff.SUBSCRIPTION_TYPE_GROUP,
            end_date__gte=timezone.now().date(),
        ).filter(Q(group=group) | Q(group__isnull=True)).order_by("end_date", "created_at").first()
        if not subscription and not force_add:
            raise ValueError("У ученика нет активного группового абонемента на курс этой группы. Если это пробное/исключение — включите ручное добавление.")
        StudentGroups.objects.get_or_create(student=student, group=group)
        if subscription and not subscription.group_id:
            subscription.group = group
            subscription.save(update_fields=["group", "updated_at"])
            SubscriptionLog.log(subscription, 'group_assigned', comment=f'Группа #{group.id}', created_by=request.user)
        elif subscription:
            SubscriptionLog.log(subscription, 'group_assigned', comment=f'Группа #{group.id}', created_by=request.user)
    except Exception as exc:
        return render(request, "crm/partials/student_drawer.html", build_student_drawer_context(request, student=student, error=str(exc)), status=400)

    student = get_student_for_drawer(student_id)
    drawer_html = render_to_string("crm/partials/student_drawer.html", build_student_drawer_context(request, student=student), request=request)
    return render_oob_response(
        "studentsTableHost",
        "crm/partials/students_table.html",
        get_students_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Ученик добавлен в группу")),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def student_remove_group_partial(request, student_id, membership_id):
    student = get_student_for_drawer(student_id)
    try:
        StudentGroups.objects.get(id=membership_id, student_id=student_id).delete()
    except StudentGroups.DoesNotExist:
        return render(request, "crm/partials/student_drawer.html", build_student_drawer_context(request, student=student, error="Связь ученика с группой не найдена"), status=400)

    student = get_student_for_drawer(student_id)
    drawer_html = render_to_string("crm/partials/student_drawer.html", build_student_drawer_context(request, student=student), request=request)
    return render_oob_response(
        "studentsTableHost",
        "crm/partials/students_table.html",
        get_students_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Ученик удалён из группы")),
    )


@login_required
@admin_required
def student_buy_tariff_modal_partial(request, student_id):
    student = get_student_for_drawer(student_id)
    return render(request, "crm/partials/student_buy_tariff_modal.html", build_buy_tariff_context(request, student))


@login_required
@admin_required
def student_payments_partial(request, student_id):
    student = get_student_for_drawer(student_id)
    return render(request, "crm/partials/student_payments.html", {"selected_student": student, "student_payments": get_student_payments(student)})


@login_required
@admin_required
@require_http_methods(["POST"])
def student_subscription_freeze_partial(request, student_id, subscription_id):
    from datetime import datetime
    from subscriptions.models import Subscription

    student = get_student_for_drawer(student_id)
    try:
        subscription = Subscription.objects.get(id=subscription_id, student=student)
        until_raw = request.POST.get("frozen_until")
        if not until_raw:
            raise ValueError("Укажите дату окончания заморозки")
        until_date = datetime.strptime(until_raw, "%Y-%m-%d").date()
        subscription.freeze(until_date, reason=(request.POST.get("freeze_reason") or "").strip(), frozen_by=request.user)
    except Exception as exc:
        return render(request, "crm/partials/student_drawer.html", build_student_drawer_context(request, student=student, error=str(exc)), status=400)

    student = get_student_for_drawer(student_id)
    drawer_html = render_to_string("crm/partials/student_drawer.html", build_student_drawer_context(request, student=student), request=request)
    return render_oob_response(
        "studentsTableHost",
        "crm/partials/students_table.html",
        get_students_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Абонемент заморожен")),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def student_subscription_unfreeze_partial(request, student_id, subscription_id):
    from subscriptions.models import Subscription

    student = get_student_for_drawer(student_id)
    try:
        subscription = Subscription.objects.get(id=subscription_id, student=student)
        subscription.unfreeze(created_by=request.user)
    except Exception as exc:
        return render(request, "crm/partials/student_drawer.html", build_student_drawer_context(request, student=student, error=str(exc)), status=400)

    student = get_student_for_drawer(student_id)
    drawer_html = render_to_string("crm/partials/student_drawer.html", build_student_drawer_context(request, student=student), request=request)
    return render_oob_response(
        "studentsTableHost",
        "crm/partials/students_table.html",
        get_students_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Абонемент разморожен")),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def student_confirm_payment_partial(request, student_id, payment_id):
    student = get_student_for_drawer(student_id)
    try:
        payment = PaymentService.confirm_offline_payment(payment_id, confirmed_by=request.user)
        if payment.subscription.student_id != student.id:
            raise ValueError("Платёж не относится к выбранному ученику")
    except Exception as exc:
        return render(request, "crm/partials/student_payments.html", {"selected_student": student, "student_payments": get_student_payments(student), "form_error": str(exc)}, status=400)
    return render_oob_response(
        "studentPaymentsHost",
        "crm/partials/student_payments.html",
        {"selected_student": student, "student_payments": get_student_payments(student)},
        request,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Оплата подтверждена")),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def student_cancel_payment_partial(request, student_id, payment_id):
    student = get_student_for_drawer(student_id)
    reason = (request.POST.get("reason") or "Оплата не поступила").strip()
    try:
        payment = PaymentService.cancel_payment(payment_id, canceled_by=request.user, reason=reason)
        if payment.subscription.student_id != student.id:
            raise ValueError("Платёж не относится к выбранному ученику")
    except Exception as exc:
        return render(request, "crm/partials/student_payments.html", {"selected_student": student, "student_payments": get_student_payments(student), "form_error": str(exc)}, status=400)
    return render_oob_response(
        "studentPaymentsHost",
        "crm/partials/student_payments.html",
        {"selected_student": student, "student_payments": get_student_payments(student)},
        request,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Платёж отменён")),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def student_buy_tariff_partial(request, student_id):
    from datetime import timedelta
    from django.utils import timezone
    from subscriptions.models import Subscription, SubscriptionLog

    student = get_student_for_drawer(student_id)
    try:
        tariff_id = request.POST.get("tariff_id")
        payment_method = request.POST.get("payment_method") or "online"
        group_id = request.POST.get("group_id")
        add_to_group = request.POST.get("add_to_group") == "on"
        if not tariff_id:
            raise ValueError("Выберите тариф")
        tariff = Tariff.objects.select_related("course").get(id=tariff_id, is_active=True)

        parent_profile = student.student_profile.parents.select_related("user").first()
        if not parent_profile:
            raise ValueError("У ученика нет привязанного родителя. Добавьте родителя в карточке ученика.")
        parent = parent_profile.user

        group = None
        if add_to_group or group_id:
            if not group_id:
                raise ValueError("Выберите группу или снимите галочку")
            group = SchoolGroups.objects.get(id=group_id)
            if group.course_id != tariff.course_id:
                raise ValueError("Курс группы не соответствует курсу тарифа")

        if tariff.subscription_type == Tariff.SUBSCRIPTION_TYPE_GROUP and not group:
            raise ValueError("Для группового абонемента нужно выбрать группу")
        if tariff.subscription_type == Tariff.SUBSCRIPTION_TYPE_INDIVIDUAL and group:
            raise ValueError("Индивидуальный абонемент не привязывается к группе")

        with transaction.atomic():
            subscription = Subscription.objects.create(
                student=student,
                parent=parent,
                tariff=tariff,
                group=group if tariff.subscription_type == Tariff.SUBSCRIPTION_TYPE_GROUP else None,
                lessons_total=tariff.lessons_count,
                lessons_used=0,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timedelta(days=tariff.validity_days),
                status="pending",
                allow_negative_lessons=tariff.allow_negative_lessons,
                negative_limit=tariff.default_negative_limit,
                allow_group_to_individual=tariff.allow_group_to_individual,
                group_to_individual_ratio=tariff.group_to_individual_ratio,
            )
            SubscriptionLog.log(subscription, 'created', comment='Оформление тарифа из CRM', created_by=request.user)
            payment_result = PaymentService.create_payment(subscription_id=subscription.id, parent_id=parent.id, payment_method=payment_method)
            payment = Payment.objects.get(id=payment_result["payment_id"])
            if group:
                payment.notes = f"{payment.notes}\nrequested_group_id={group.id}".strip()
                payment.save(update_fields=["notes", "updated_at"])
            if group and subscription.status == "active":
                StudentGroups.objects.get_or_create(student=student, group=group)
    except Exception as exc:
        return render(request, "crm/partials/student_buy_tariff_modal.html", build_buy_tariff_context(request, student, data=request.POST, error=str(exc)), status=400)

    student = get_student_for_drawer(student_id)
    drawer_html = render_to_string("crm/partials/student_drawer.html", build_student_drawer_context(request, student=student), request=request)
    modal_html = render_to_string("crm/partials/student_buy_tariff_modal.html", build_buy_tariff_context(request, student), request=request)
    toast = "Подписка создана. Платёж ожидает подтверждения."
    if payment_method == "online" and payment_result.get("payment_url"):
        toast = "Подписка создана. Откройте ссылку онлайн-оплаты."
    return render_oob_response(
        "studentsTableHost",
        "crm/partials/students_table.html",
        get_students_context(request),
        request,
        drawer_html=drawer_html + modal_html,
        triggers=hx_trigger("crm:close-buy-tariff-modal", "crm:refresh-stats", toast=crm_toast(toast, title="Тариф оформлен")),
    )


@login_required
@admin_required
def teachers_table_partial(request):
    return render(request, "crm/partials/teachers_table.html", get_teachers_context(request))


@login_required
@admin_required
def teacher_drawer_partial(request, teacher_id=None):
    teacher = get_teacher_for_drawer(teacher_id) if teacher_id else None
    return render(request, "crm/partials/teacher_drawer.html", get_teachers_context(request, selected_teacher=teacher))


@login_required
@admin_required
@require_http_methods(["POST"])
def teacher_save_partial(request, teacher_id=None):
    teacher = get_teacher_for_drawer(teacher_id) if teacher_id else None
    try:
        payload = validate_teacher_payload(request.POST, teacher=teacher, creating=teacher is None)
        if teacher is None:
            password = payload.pop("password")
            payload.pop("is_active", None)
            teacher = CustomUser.objects.create_user(role=UserRole.TEACHER, password=password, **payload)
            TeacherProfile.objects.get_or_create(user=teacher)
        else:
            payload.pop("password", None)
            for field, value in payload.items():
                setattr(teacher, field, value)
            teacher.save()
    except Exception as exc:
        return render(request, "crm/partials/teacher_drawer.html", get_teachers_context(request, selected_teacher=teacher, error=str(exc)), status=400)

    teacher = get_teacher_for_drawer(teacher.id)
    drawer_html = render_to_string("crm/partials/teacher_drawer.html", get_teachers_context(request, selected_teacher=teacher), request=request)
    return render_oob_response(
        "teachersTableHost",
        "crm/partials/teachers_table.html",
        get_teachers_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Данные учителя сохранены")),
    )


@login_required
@admin_required
def groups_table_partial(request):
    return render(request, "crm/partials/groups_table.html", get_groups_context(request))


@login_required
@admin_required
def group_drawer_partial(request, group_id=None):
    group = get_group_for_drawer(group_id) if group_id else None
    return render(request, "crm/partials/group_drawer.html", get_groups_context(request, selected_group=group))


@login_required
@admin_required
@require_http_methods(["POST"])
def group_save_partial(request, group_id=None):
    group = get_group_for_drawer(group_id) if group_id else None
    try:
        group = save_group_from_post(request, group)
        default_time = request.POST.get("default_lesson_time")
        if default_time and group_id is None:
            from datetime import datetime
            duration = int(request.POST.get("default_lesson_duration") or 90)
            lessons_count = 1 if duration == 45 else 2
            GroupScheduleTemplate.objects.create(group=group, weekday=0, start_time=datetime.strptime(default_time, "%H:%M").time(), lessons_count=lessons_count, is_active=True)
    except Exception as exc:
        return render(request, "crm/partials/group_drawer.html", get_groups_context(request, selected_group=group, error=str(exc), data=request.POST), status=400)

    group = get_group_for_drawer(group.id)
    drawer_html = render_to_string("crm/partials/group_drawer.html", get_groups_context(request, selected_group=group), request=request)
    return render_oob_response("groupsTableHost", "crm/partials/groups_table.html", get_groups_context(request), request, drawer_html=drawer_html, triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Группа сохранена")))


@login_required
@admin_required
@require_http_methods(["POST"])
def group_template_save_partial(request, group_id):
    group = get_group_for_drawer(group_id)
    try:
        GroupScheduleTemplate.objects.create(group=group, weekday=int(request.POST.get("weekday")), start_time=request.POST.get("start_time"), lessons_count=int(request.POST.get("lessons_count") or 2), is_active=True)
    except Exception as exc:
        return render(request, "crm/partials/group_schedule_modal.html", {"selected_group": group, "form_error": str(exc)}, status=400)
    group = get_group_for_drawer(group_id)
    drawer_html = render_to_string("crm/partials/group_drawer.html", get_groups_context(request, selected_group=group), request=request)
    modal_html = render_to_string("crm/partials/group_schedule_modal.html", {"selected_group": group}, request=request)
    return render_oob_response("groupsTableHost", "crm/partials/groups_table.html", get_groups_context(request), request, drawer_html=drawer_html + modal_html, triggers=hx_trigger("crm:close-schedule-template-modal", toast=crm_toast("Стандартное время добавлено")))


@login_required
@admin_required
@require_http_methods(["POST"])
def group_template_delete_partial(request, group_id, template_id):
    group = get_group_for_drawer(group_id)
    try:
        GroupScheduleTemplate.objects.get(id=template_id, group=group).delete()
    except GroupScheduleTemplate.DoesNotExist:
        pass
    group = get_group_for_drawer(group_id)
    drawer_html = render_to_string("crm/partials/group_drawer.html", get_groups_context(request, selected_group=group), request=request)
    return render_oob_response("groupsTableHost", "crm/partials/groups_table.html", get_groups_context(request), request, drawer_html=drawer_html, triggers=hx_trigger(toast=crm_toast("Стандартное время удалено")))


@login_required
@admin_required
def messages_tickets_partial(request):
    return render(request, "crm/partials/messages_sidebar.html", get_messages_context(request))


@login_required
@admin_required
def messages_chat_partial(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.select_related("parent", "assigned_admin").prefetch_related("messages", "messages__sender"), id=ticket_id)
    Message.objects.filter(ticket=ticket, is_read=False).exclude(sender=request.user).update(is_read=True)
    ticket = Ticket.objects.select_related("parent", "assigned_admin").prefetch_related("messages", "messages__sender").get(id=ticket.id)
    response = HttpResponse(
        render_to_string("crm/partials/messages_chat.html", get_messages_context(request, selected_ticket=ticket), request=request)
        + render_to_string("crm/partials/messages_sidebar.html", {**get_messages_context(request, selected_ticket=ticket), "sidebar_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger("crm:refresh-stats")
    return response


@login_required
@admin_required
@require_http_methods(["POST"])
def messages_send_partial(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    content = (request.POST.get("content") or "").strip()
    if not content:
        return render(request, "crm/partials/messages_chat.html", get_messages_context(request, selected_ticket=ticket, error="Введите сообщение"), status=400)
    message = Message.objects.create(ticket=ticket, sender=request.user, content=content)
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{ticket.parent_id}",
                {"type": "new_message", "message": {"id": message.id, "ticket_id": ticket.id, "sender_id": request.user.id, "sender_name": request.user.get_full_name(), "content": message.content, "created_at": message.created_at.isoformat(), "is_read": message.is_read}},
            )
    except Exception:
        pass
    ticket = Ticket.objects.select_related("parent", "assigned_admin").prefetch_related("messages", "messages__sender").get(id=ticket.id)
    response = HttpResponse(
        render_to_string("crm/partials/messages_chat.html", get_messages_context(request, selected_ticket=ticket), request=request)
        + render_to_string("crm/partials/messages_sidebar.html", {**get_messages_context(request, selected_ticket=ticket), "sidebar_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger("crm:refresh-stats")
    return response


@login_required
@admin_required
@require_http_methods(["POST"])
def messages_close_partial(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    try:
        ticket.close(request.user)
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"user_{ticket.parent_id}",
                    {"type": "ticket_closed", "ticket": {"id": ticket.id, "status": ticket.status}},
                )
        except Exception:
            pass
    except Exception as exc:
        return render(request, "crm/partials/messages_chat.html", get_messages_context(request, selected_ticket=ticket, error=str(exc)), status=400)
    ticket.refresh_from_db()
    response = HttpResponse(
        render_to_string("crm/partials/messages_chat.html", get_messages_context(request, selected_ticket=ticket), request=request)
        + render_to_string("crm/partials/messages_sidebar.html", {**get_messages_context(request, selected_ticket=ticket), "sidebar_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger("crm:refresh-stats", toast=crm_toast("Обращение закрыто"))
    return response


@login_required
@admin_required
def requests_table_partial(request):
    return render(request, "crm/partials/requests_table.html", get_requests_context(request))


@login_required
@admin_required
def request_drawer_partial(request, request_id):
    participant_request = get_request_for_drawer(request_id)
    return render(request, "crm/partials/request_drawer.html", build_request_drawer_context(request, participant_request=participant_request))


@login_required
@admin_required
@require_http_methods(["POST"])
def request_mark_processed_partial(request, request_id):
    participant_request = get_request_for_drawer(request_id)
    participant_request.checked = True
    participant_request.save(update_fields=["checked"])

    drawer_html = render_to_string(
        "crm/partials/request_drawer.html",
        build_request_drawer_context(request, participant_request=participant_request),
        request=request,
    )
    return render_oob_response(
        "requestsTableHost",
        "crm/partials/requests_table.html",
        get_requests_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Заявка отмечена обработанной")),
    )


@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def request_create_student_partial(request, request_id):
    participant_request = get_request_for_drawer(request_id)

    if request.method == "GET":
        return render(
            request,
            "crm/partials/request_student_drawer.html",
            build_student_from_request_context(request, participant_request=participant_request),
        )

    try:
        with transaction.atomic():
            result, error = create_student_with_parent(request.POST)
            if error:
                raise ValueError(error.get("error") or serializer_errors_to_text(error))

            participant_request.checked = True
            participant_request.save(update_fields=["checked"])
    except Exception as exc:
        return render(
            request,
            "crm/partials/request_student_drawer.html",
            build_student_from_request_context(
                request,
                participant_request=participant_request,
                data=request.POST,
                error=str(exc),
            ),
            status=400,
        )

    participant_request = get_request_for_drawer(request_id)

    student = result["student"]
    drawer_html = render_to_string(
        "crm/partials/request_drawer.html",
        build_request_drawer_context(request, participant_request=participant_request),
        request=request,
    )
    student_drawer_html = render_to_string(
        "crm/partials/request_student_drawer.html",
        build_student_from_request_context(request, participant_request=participant_request),
        request=request,
    )
    toast_text = f"Ученик {student.last_name} {student.first_name} создан. Логин: {student.username}"
    return render_oob_response(
        "requestsTableHost",
        "crm/partials/requests_table.html",
        get_requests_context(request),
        request,
        drawer_html=drawer_html + student_drawer_html,
        triggers=hx_trigger(
            "crm:close-student-drawer",
            "crm:close-request-drawer",
            "crm:refresh-stats",
            toast=crm_toast(toast_text, title="Ученик создан"),
        ),
    )


@login_required
@admin_required
def subscriptions_table_partial(request):
    return render(request, "crm/partials/subscriptions_table.html", get_subscriptions_context(request))


@login_required
@admin_required
@require_http_methods(["POST"])
def subscriptions_check_partial(request):
    from subscriptions.services import SubscriptionMonitoringService

    result = SubscriptionMonitoringService.run_daily_check(created_by=request.user)
    message = (
        f"Проверка завершена: истекших обновлено — {result['expired_updated']}, "
        f"исчерпанных — {result['exhausted_updated']}."
    )
    response = render(request, "crm/partials/subscriptions_table.html", {**get_subscriptions_context(request), "monitoring_result": result})
    response["HX-Trigger"] = hx_trigger("crm:refresh-stats", toast=crm_toast(message, title="Абонементы проверены"))
    return response


@login_required
@admin_required
def subscription_drawer_partial(request, subscription_id):
    subscription = get_subscription_for_drawer(subscription_id)
    return render(request, "crm/partials/subscription_drawer.html", get_subscriptions_context(request, subscription=subscription))


def subscription_oob_response(request, subscription, toast_message):
    subscription = get_subscription_for_drawer(subscription.id)
    drawer_html = render_to_string(
        "crm/partials/subscription_drawer.html",
        get_subscriptions_context(request, subscription=subscription),
        request=request,
    )
    return render_oob_response(
        "subscriptionsTableHost",
        "crm/partials/subscriptions_table.html",
        get_subscriptions_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast(toast_message)),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def subscription_freeze_partial(request, subscription_id):
    try:
        subscription = get_subscription_for_drawer(subscription_id)
        until_raw = request.POST.get("frozen_until")
        if not until_raw:
            raise ValueError("Укажите дату окончания заморозки")
        until_date = datetime.strptime(until_raw, "%Y-%m-%d").date()
        subscription.freeze(until_date, reason=(request.POST.get("freeze_reason") or "").strip(), frozen_by=request.user)
    except Exception as exc:
        subscription = get_subscription_for_drawer(subscription_id)
        return render(request, "crm/partials/subscription_drawer.html", get_subscriptions_context(request, subscription=subscription, error=str(exc)), status=400)
    return subscription_oob_response(request, subscription, "Абонемент заморожен")


@login_required
@admin_required
@require_http_methods(["POST"])
def subscription_unfreeze_partial(request, subscription_id):
    try:
        subscription = get_subscription_for_drawer(subscription_id)
        subscription.unfreeze(created_by=request.user)
    except Exception as exc:
        subscription = get_subscription_for_drawer(subscription_id)
        return render(request, "crm/partials/subscription_drawer.html", get_subscriptions_context(request, subscription=subscription, error=str(exc)), status=400)
    return subscription_oob_response(request, subscription, "Абонемент разморожен")


@login_required
@admin_required
@require_http_methods(["POST"])
def subscription_close_partial(request, subscription_id):
    try:
        subscription = get_subscription_for_drawer(subscription_id)
        close_action = request.POST.get("close_action") or "canceled"
        reason = (request.POST.get("close_reason") or "").strip()
        if close_action not in ["canceled", "completed"]:
            raise ValueError("Выберите корректное действие")
        if not reason:
            raise ValueError("Укажите причину закрытия абонемента")
        subscription.close(status=close_action, reason=reason, closed_by=request.user)
        subscription.student.update_active_status()
        subscription.parent.update_active_status()
    except Exception as exc:
        subscription = get_subscription_for_drawer(subscription_id)
        return render(request, "crm/partials/subscription_drawer.html", get_subscriptions_context(request, subscription=subscription, error=str(exc)), status=400)

    message = "Абонемент отменен" if close_action == "canceled" else "Абонемент завершен вручную"
    return subscription_oob_response(request, subscription, message)


@login_required
@admin_required
def payments_table_partial(request):
    return render(request, "crm/partials/payments_table.html", get_payments_context(request))


@login_required
@admin_required
def payment_drawer_partial(request, payment_id):
    payment = get_payment_for_drawer(payment_id)
    return render(request, "crm/partials/payment_drawer.html", build_payment_drawer_context(request, payment=payment))


def payment_oob_response(request, payment, toast_message):
    drawer_html = render_to_string(
        "crm/partials/payment_drawer.html",
        build_payment_drawer_context(request, payment=payment),
        request=request,
    )
    return render_oob_response(
        "paymentsTableHost",
        "crm/partials/payments_table.html",
        get_payments_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger(toast=crm_toast(toast_message)),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def payment_confirm_partial(request, payment_id):
    try:
        payment = PaymentService.confirm_offline_payment(payment_id, confirmed_by=request.user)
    except Exception as exc:
        payment = get_payment_for_drawer(payment_id)
        return render(
            request,
            "crm/partials/payment_drawer.html",
            build_payment_drawer_context(request, payment=payment, error=str(exc)),
            status=400,
        )
    return payment_oob_response(request, payment, "Оплата подтверждена")


@login_required
@admin_required
@require_http_methods(["POST"])
def payment_cancel_partial(request, payment_id):
    reason = (request.POST.get("reason") or "Оплата не поступила").strip()
    try:
        payment = PaymentService.cancel_payment(payment_id, canceled_by=request.user, reason=reason)
    except Exception as exc:
        payment = get_payment_for_drawer(payment_id)
        return render(
            request,
            "crm/partials/payment_drawer.html",
            build_payment_drawer_context(request, payment=payment, error=str(exc)),
            status=400,
        )
    return payment_oob_response(request, payment, "Платеж отменён")


def build_parent_drawer_context(request, parent=None, error=None):
    if parent is not None:
        serialized = ParentListSerializer(parent).data
        form = {
            "first_name": serialized.get("first_name") or "",
            "last_name": serialized.get("last_name") or "",
            "username": serialized.get("username") or "",
            "phone": serialized.get("phone") or "",
            "email": serialized.get("email") or "",
            "is_active": parent.is_active,
        }
        title = f"Родитель #{parent.id}"
        subtitle = serialized.get("username") or ""
        submit_label = "Сохранить"
    else:
        serialized = None
        form = {
            "first_name": "",
            "last_name": "",
            "username": "",
            "phone": "",
            "email": "",
            "is_active": True,
        }
        title = "Карточка родителя"
        subtitle = ""
        submit_label = "Сохранить"

    return {
        **get_parents_context(request),
        "selected_parent": serialized,
        "parent_form": form,
        "drawer_title": title,
        "drawer_subtitle": subtitle,
        "submit_label": submit_label,
        "form_action": reverse("crm:parent_save_edit", args=[parent.id]) if parent else "",
        "form_error": error,
    }


@login_required
@admin_required
def parents_table_partial(request):
    return render(request, "crm/partials/parents_table.html", get_parents_context(request))


@login_required
@admin_required
def parent_drawer_partial(request, parent_id):
    parent = get_object_or_404(CustomUser.objects.prefetch_related(
        "parent_profile__students",
        "parent_profile__students__user",
    ), id=parent_id, role=UserRole.PARENT)
    return render(request, "crm/partials/parent_drawer.html", build_parent_drawer_context(request, parent=parent))


@login_required
@admin_required
@require_http_methods(["POST"])
def parent_save_partial(request, parent_id):
    parent = get_object_or_404(CustomUser, id=parent_id, role=UserRole.PARENT)
    serializer = ParentUpdateSerializer(parent, data=request.POST, partial=True)

    if not serializer.is_valid():
        error_text = serializer_errors_to_text(serializer.errors)
        return render(
            request,
            "crm/partials/parent_drawer.html",
            build_parent_drawer_context(request, parent=parent, error=error_text),
            status=400,
        )

    serializer.save()
    updated_parent = CustomUser.objects.prefetch_related(
        "parent_profile__students",
        "parent_profile__students__user",
    ).get(id=parent.id)

    updated_context = get_parents_context(request)
    drawer_html = render_to_string(
        "crm/partials/parent_drawer.html",
        build_parent_drawer_context(request, parent=updated_parent),
        request=request,
    )
    return render_oob_response(
        "parentsTableHost",
        "crm/partials/parents_table.html",
        updated_context,
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger(
            "crm:close-parent-drawer",
            "crm:refresh-stats",
            toast=crm_toast("Данные родителя сохранены"),
        ),
    )


@login_required
@admin_required
def tariffs_view(request):
    return render(request, "crm/tariffs.html", get_tariffs_context(request))


def build_tariff_form_values(tariff=None, data=None):
    data = data or {}

    def get_text(field, default=""):
        if field == "course":
            if data.get(field) not in (None, ""):
                return str(data.get(field))
            if tariff is not None and getattr(tariff, field, None) is not None:
                return str(getattr(tariff, field).id)
            return default

        value = data.get(field)
        if value not in (None, ""):
            return str(value)
        if tariff is not None:
            value = getattr(tariff, field, default)
            if value is not None:
                return str(value)
        return default

    return {
        "name": get_text("name"),
        "course": get_text("course"),
        "subscription_type": get_text("subscription_type", Tariff.SUBSCRIPTION_TYPE_GROUP),
        "lessons_count": get_text("lessons_count"),
        "validity_days": get_text("validity_days"),
        "price": get_text("price", "0.00"),
        "description": get_text("description"),
        "is_trial": (data.get("is_trial") == "on") if data else bool(getattr(tariff, "is_trial", False)),
        "is_active": (data.get("is_active") == "on") if data else (bool(getattr(tariff, "is_active", True)) if tariff else True),
    }


def build_tariff_drawer_context(request, tariff=None, data=None, error=None):
    is_edit = tariff is not None
    return {
        **get_tariffs_context(request, tariff=tariff),
        "selected_tariff": tariff,
        "tariff_form": build_tariff_form_values(tariff=tariff, data=data),
        "drawer_title": "Редактировать тариф" if is_edit else "Создать тариф",
        "drawer_subtitle": f"{tariff.course.name} · {tariff.lessons_count} занятий" if is_edit else "Заполните параметры тарифа",
        "submit_label": "Сохранить" if is_edit else "Создать",
        "form_action": reverse("crm:tariff_save_edit", args=[tariff.id]) if is_edit else reverse("crm:tariff_save_create"),
        "form_error": error,
    }


def get_tariffs_queryset(request):
    tariffs = Tariff.objects.select_related("course").order_by("course__name", "name")
    search = (request.GET.get("search") or "").strip()
    course = request.GET.get("course") or ""
    active = request.GET.get("active") or ""
    subscription_type = request.GET.get("subscription_type") or ""
    trial = request.GET.get("trial") or ""

    if search:
        tariffs = tariffs.filter(
            Q(name__icontains=search)
            | Q(course__name__icontains=search)
            | Q(description__icontains=search)
        ).distinct()
    if course:
        tariffs = tariffs.filter(course_id=course)
    if active:
        tariffs = tariffs.filter(is_active=active == "true")
    if subscription_type:
        tariffs = tariffs.filter(subscription_type=subscription_type)
    if trial == "trial":
        tariffs = tariffs.filter(is_trial=True)
    elif trial == "paid":
        tariffs = tariffs.filter(is_trial=False)

    return tariffs


def get_tariffs_context(request, tariff=None):
    tariffs = get_tariffs_queryset(request)
    return {
        "tariffs": tariffs,
        "tariffs_count": tariffs.count(),
        "courses": Courses.objects.all().order_by("name"),
        "selected_tariff": tariff,
        "subscription_type_choices": Tariff.SUBSCRIPTION_TYPE_CHOICES,
    }


def get_courses_queryset(request):
    courses = Courses.objects.all()
    search = (request.GET.get("search") or "").strip()
    sort = request.GET.get("sort") or "name_az"

    if search:
        courses = courses.filter(name__icontains=search)

    if sort == "name_za":
        courses = courses.order_by("-name")
    else:
        courses = courses.order_by("name")

    return courses


def get_courses_context(request, course=None):
    courses = get_courses_queryset(request)
    return {
        "courses": courses,
        "courses_count": courses.count(),
        "selected_course": course,
    }


def build_course_drawer_context(request, course=None, data=None, error=None):
    data = data or {}
    is_edit = course is not None
    course_name = data.get("name") or (course.name if course else "")

    return {
        **get_courses_context(request, course=course),
        "selected_course": course,
        "course_form": {"name": course_name},
        "drawer_title": f"Курс #{course.id}" if is_edit else "Добавить курс",
        "drawer_subtitle": course.name if is_edit else "Создание нового курса в системе",
        "submit_label": "Сохранить" if is_edit else "Сохранить курс",
        "form_action": reverse("crm:course_save_edit", args=[course.id]) if is_edit else reverse("crm:course_save_create"),
        "form_error": error,
    }


@login_required
@admin_required
def courses_table_partial(request):
    return render(request, "crm/partials/courses_table.html", get_courses_context(request))


@login_required
@admin_required
def course_drawer_partial(request, course_id=None):
    course = get_object_or_404(Courses, id=course_id) if course_id else None
    return render(request, "crm/partials/course_drawer.html", build_course_drawer_context(request, course=course))


@login_required
@admin_required
@require_http_methods(["POST"])
def course_save_partial(request, course_id=None):
    course = get_object_or_404(Courses, id=course_id) if course_id else None
    data = request.POST
    name = (data.get("name") or "").strip()

    try:
        if not name:
            raise ValueError("Название курса обязательно")

        duplicate = Courses.objects.filter(name__iexact=name)
        if course is not None:
            duplicate = duplicate.exclude(id=course.id)
        if duplicate.exists():
            raise ValueError("Курс с таким названием уже существует")

        if course is None:
            course = Courses.objects.create(name=name)
        else:
            course.name = name
            course.save()
    except Exception as exc:
        return render(
            request,
            "crm/partials/course_drawer.html",
            build_course_drawer_context(request, course=course, data=data, error=str(exc)),
            status=400,
        )

    drawer_html = render_to_string("crm/partials/course_drawer.html", build_course_drawer_context(request), request=request)
    return render_oob_response(
        "coursesTableHost",
        "crm/partials/courses_table.html",
        get_courses_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger(
            "crm:close-course-drawer",
            "crm:refresh-stats",
            toast=crm_toast("Курс сохранён"),
        ),
    )


@login_required
@admin_required
@require_http_methods(["POST"])
def course_delete_partial(request, course_id):
    course = get_object_or_404(Courses, id=course_id)
    try:
        course.delete()
    except Exception:
        return render(
            request,
            "crm/partials/course_drawer.html",
            build_course_drawer_context(request, course=course, error="Не удалось удалить курс. Возможно, он используется в группах или тарифах."),
            status=400,
        )

    drawer_html = render_to_string("crm/partials/course_drawer.html", build_course_drawer_context(request), request=request)
    return render_oob_response(
        "coursesTableHost",
        "crm/partials/courses_table.html",
        get_courses_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger(
            "crm:close-course-drawer",
            "crm:refresh-stats",
            toast=crm_toast("Курс удалён"),
        ),
    )


@login_required
@admin_required
def tariffs_table_partial(request):
    return render(request, "crm/partials/tariffs_table.html", get_tariffs_context(request))


@login_required
@admin_required
def tariff_drawer_partial(request, tariff_id=None):
    tariff = get_object_or_404(Tariff, id=tariff_id) if tariff_id else None
    return render(request, "crm/partials/tariff_drawer.html", build_tariff_drawer_context(request, tariff=tariff))


@login_required
@admin_required
@require_http_methods(["POST"])
def tariff_save_partial(request, tariff_id=None):
    tariff = get_object_or_404(Tariff, id=tariff_id) if tariff_id else None
    data = request.POST

    try:
        course = Courses.objects.filter(id=data.get("course")).first()
        if course is None:
            raise ValueError("Выберите курс")

        payload = {
            "name": (data.get("name") or "").strip(),
            "course": course,
            "subscription_type": data.get("subscription_type") or Tariff.SUBSCRIPTION_TYPE_GROUP,
            "lessons_count": int(data.get("lessons_count") or 0),
            "validity_days": int(data.get("validity_days") or 0),
            "price": data.get("price") or "0.00",
            "description": (data.get("description") or "").strip(),
            "is_trial": data.get("is_trial") == "on",
            "is_active": data.get("is_active") == "on",
        }
        if not payload["name"] or payload["lessons_count"] < 1 or payload["validity_days"] < 1:
            raise ValueError("Заполните название, количество занятий и срок действия")

        if tariff is None:
            tariff = Tariff.objects.create(**payload)
        else:
            for field, value in payload.items():
                setattr(tariff, field, value)
            tariff.save()
    except Exception as exc:
        context = build_tariff_drawer_context(request, tariff=tariff, data=data, error=str(exc))
        return render(request, "crm/partials/tariff_drawer.html", context, status=400)

    drawer_html = render_to_string(
        "crm/partials/tariff_drawer.html",
        build_tariff_drawer_context(request),
        request=request,
    )
    return render_oob_response(
        "tariffsTableHost",
        "crm/partials/tariffs_table.html",
        get_tariffs_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger(
            "crm:close-drawer",
            "crm:refresh-stats",
            toast=crm_toast("Тариф сохранён"),
        ),
    )
