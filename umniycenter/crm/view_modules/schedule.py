from .common import *


def schedule_view(request):
    today = timezone.localdate()
    return render(request, "crm/schedule.html", {
        "groups": SchoolGroups.objects.select_related("course", "teacher").filter(is_active=True).order_by("course__name", "number"),
        "schedule_templates": GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher").order_by("group__course__name", "group__number", "weekday", "start_time"),
        "schedule_defaults": {
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=30)).isoformat(),
        },
    })


def get_schedule_queryset(request):
    lessons = Schedule.objects.select_related("group", "group__course", "teacher", "student", "course").order_by("classdateStart")
    today = timezone.localdate()
    date_from = request.GET.get("date_from") or today.isoformat()
    date_to = request.GET.get("date_to") or (today + timedelta(days=30)).isoformat()
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
    pagination = get_pagination(request, get_schedule_queryset(request))
    lessons = [prepare_schedule_lesson(lesson) for lesson in pagination["items"]]
    if selected_lesson:
        selected_lesson = prepare_schedule_lesson(selected_lesson)
    return {
        "lessons": lessons,
        **pagination,
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


def schedule_today_lessons_partial(request):
    return render(request, "crm/partials/schedule_today_lessons.html", get_schedule_today_context(request))


def schedule_today_attendance_partial(request, lesson_id):
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "teacher", "student", "course"), id=lesson_id)
    return render(request, "crm/partials/schedule_today_attendance.html", get_schedule_today_context(request, selected_lesson=lesson))


def schedule_today_student_partial(request, lesson_id, student_id):
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "teacher", "student", "course"), id=lesson_id)
    student = get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)
    return render(request, "crm/partials/schedule_today_student.html", get_schedule_today_context(request, selected_lesson=lesson, selected_student=student))


def schedule_lessons_partial(request):
    context = get_schedule_context(request)
    template = "crm/partials/schedule_lesson_cards.html" if context["is_load_more"] else "crm/partials/schedule_lessons.html"
    return render(request, template, context)


def schedule_lesson_drawer_partial(request, lesson_id):
    lesson = get_object_or_404(Schedule.objects.select_related("group", "group__course", "teacher", "student", "course"), id=lesson_id)
    context = {**get_schedule_context(request, selected_lesson=lesson), **get_lesson_attendance_context(request, lesson)}
    return render(request, "crm/partials/schedule_lesson_drawer.html", context)


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


def schedule_template_partial(request, template_id=None):
    template = None
    if template_id:
        template = get_object_or_404(GroupScheduleTemplate.objects.select_related("group", "group__course", "group__teacher"), id=template_id)
    return render(request, "crm/partials/schedule_template_modal.html", get_schedule_template_context(request, selected_template=template))


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


def schedule_template_delete_partial(request, template_id):
    template = get_object_or_404(GroupScheduleTemplate, id=template_id)
    template.delete()
    response = HttpResponse(render_to_string("crm/partials/schedule_templates.html", get_schedule_context(request), request=request))
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Стандартное время удалено"))
    return response


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


def schedule_create_lesson_drawer_partial(request):
    return render(request, "crm/partials/schedule_create_lesson_drawer.html", get_create_lesson_context(request))


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


protect_crm_views(
    globals(),
    "schedule_view",
    "schedule_today_view",
    "schedule_today_lessons_partial",
    "schedule_today_attendance_partial",
    "schedule_today_student_partial",
    "schedule_lessons_partial",
    "schedule_lesson_drawer_partial",
    "schedule_lesson_cancel_partial",
    "schedule_lesson_reschedule_partial",
    "schedule_template_partial",
    "schedule_template_save_partial",
    "schedule_template_delete_partial",
    "schedule_generate_partial",
    "schedule_create_lesson_drawer_partial",
    "schedule_lesson_create_partial",
    "schedule_attendance_mark_partial",
    "schedule_attendance_cancel_partial",
)
