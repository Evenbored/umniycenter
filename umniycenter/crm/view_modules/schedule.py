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
    lessons = Lesson.objects.select_related("group", "group__course", "teacher", "course").prefetch_related("participants", "participants__student", "order_items", "order_items__order").order_by("starts_at")
    today = timezone.localdate()
    date_from = request.GET.get("date_from") or today.isoformat()
    date_to = request.GET.get("date_to") or (today + timedelta(days=30)).isoformat()
    group_id = request.GET.get("group")
    status_filter = request.GET.get("status")

    if date_from:
        lessons = lessons.filter(starts_at__date__gte=date_from)
    if date_to:
        lessons = lessons.filter(starts_at__date__lte=date_to)
    if group_id:
        lessons = lessons.filter(group_id=group_id)
    if status_filter:
        if status_filter in ["cancelled", "rescheduled"]:
            lessons = lessons.filter(status=status_filter)
        else:
            if status_filter == "completed":
                lessons = lessons.filter(ends_at__lt=timezone.now()).exclude(status="cancelled")
            elif status_filter == "scheduled":
                lessons = lessons.filter(ends_at__gte=timezone.now(), status="scheduled")

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
        "selected_lesson_orders": selected_lesson.order_items.select_related("order").all() if selected_lesson else [],
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
    lesson_type = request.GET.get("lesson_type") or request.POST.get("lesson_type") or (Lesson.LessonType.GROUP if group_id else Lesson.LessonType.INDIVIDUAL)
    subscription_type = "group" if group_id else "individual"
    students = CustomUser.objects.filter(role=UserRole.STUDENT, is_active=True)
    if group_id:
        students = students.filter(studentgroups__group_id=group_id)
    if course_id and lesson_type not in [Lesson.LessonType.SINGLE_GROUP, Lesson.LessonType.SINGLE_INDIVIDUAL, Schedule.LESSON_TYPE_SINGLE]:
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
        "single_lesson_amount": request.POST.get("single_lesson_amount") or request.GET.get("single_lesson_amount") or "",
        "single_lesson_payment_method": request.POST.get("single_lesson_payment_method") or request.GET.get("single_lesson_payment_method") or "cash",
        "single_lesson_paid": request.POST.get("single_lesson_paid") != "off",
        "create_students": students.distinct().order_by("last_name", "first_name", "id"),
        "create_groups": context["groups"].filter(course_id=course_id) if course_id else SchoolGroups.objects.none(),
        "teachers": CustomUser.objects.filter(role=UserRole.TEACHER, is_active=True).order_by("last_name", "first_name", "id"),
        "courses": Courses.objects.all().order_by("name"),
        "payment_method_choices": Payment.PAYMENT_METHOD_CHOICES,
    })
    return context


def get_lesson_attendance_context(request, lesson, error=None, success=None):
    participants = list(lesson.participants.select_related("student", "subscription").order_by("student__last_name", "student__first_name"))
    students = [participant.student for participant in participants]
    participant_by_student = {participant.student_id: participant for participant in participants}
    attendance_rows = [{"student": participant.student, "attendance": participant, "participant": participant} for participant in participants]

    return {
        "selected_lesson": prepare_schedule_lesson(lesson),
        "attendance_students": students,
        "attendance_rows": attendance_rows,
        "attendance_by_student": participant_by_student,
        "attendance_status_choices": LessonParticipant.AttendanceStatus.choices,
        "form_error": error,
        "form_success": success,
    }


def schedule_today_view(request):
    return render(request, "crm/schedule_today.html", get_schedule_today_context(request))


def get_schedule_today_context(request, selected_lesson=None, selected_student=None, error=None, success=None):
    today = timezone.localdate()
    lessons = [
        prepare_schedule_lesson(lesson)
        for lesson in Lesson.objects.select_related("group", "group__course", "teacher", "course").prefetch_related("participants")
        .filter(starts_at__date=today)
        .order_by("starts_at")
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
    lesson = get_object_or_404(Lesson.objects.select_related("group", "group__course", "teacher", "course"), id=lesson_id)
    return render(request, "crm/partials/schedule_today_attendance.html", get_schedule_today_context(request, selected_lesson=lesson))


def schedule_today_student_partial(request, lesson_id, student_id):
    lesson = get_object_or_404(Lesson.objects.select_related("group", "group__course", "teacher", "course"), id=lesson_id)
    student = get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)
    return render(request, "crm/partials/schedule_today_student.html", get_schedule_today_context(request, selected_lesson=lesson, selected_student=student))


def schedule_lessons_partial(request):
    context = get_schedule_context(request)
    template = "crm/partials/schedule_lesson_cards.html" if context["is_load_more"] else "crm/partials/schedule_lessons.html"
    return render(request, template, context)


def schedule_lesson_drawer_partial(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related("group", "group__course", "teacher", "course"), id=lesson_id)
    context = {**get_schedule_context(request, selected_lesson=lesson), **get_lesson_attendance_context(request, lesson)}
    return render(request, "crm/partials/schedule_lesson_drawer.html", context)


def schedule_lesson_cancel_partial(request, lesson_id):
    from schedule.services import LessonService
    lesson = get_object_or_404(Lesson, id=lesson_id)
    LessonService.cancel_lesson(lesson, (request.POST.get("reason") or "").strip(), request.user)
    lesson = Lesson.objects.select_related("group", "group__course", "teacher", "course").get(id=lesson.id)
    response = HttpResponse(
        render_to_string("crm/partials/schedule_lesson_drawer.html", {**get_schedule_context(request, selected_lesson=lesson), **get_lesson_attendance_context(request, lesson)}, request=request)
        + render_to_string("crm/partials/schedule_lessons.html", {**get_schedule_context(request), "lessons_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Занятие отменено"))
    return response


def schedule_lesson_reschedule_partial(request, lesson_id):
    from schedule.services import LessonService
    lesson = get_object_or_404(Lesson, id=lesson_id)
    try:
        new_start_raw = request.POST.get("classdateStart") or ""
        new_start = datetime.fromisoformat(new_start_raw)
        if timezone.is_naive(new_start):
            new_start = timezone.make_aware(new_start)
        lessons_count = int(request.POST.get("lessons_count") or 2)
        lesson_type = request.POST.get("lesson_type") or lesson.lesson_type
        if lesson_type == Schedule.LESSON_TYPE_REGULAR:
            lesson_type = Lesson.LessonType.GROUP if lesson.group_id else Lesson.LessonType.INDIVIDUAL
        elif lesson_type == Schedule.LESSON_TYPE_SINGLE:
            lesson_type = Lesson.LessonType.SINGLE_GROUP if lesson.group_id else Lesson.LessonType.SINGLE_INDIVIDUAL
        if lessons_count not in (1, 2):
            raise ValueError("Занятие может длиться только 1 или 2 академических часа")
        if lesson_type not in dict(Lesson.LessonType.choices):
            raise ValueError("Выберите корректный тип занятия")
        from schedule.services import get_lesson_end_time
        from datetime import datetime as dt
        end_time = get_lesson_end_time(new_start.time(), lessons_count)
        new_end = timezone.make_aware(dt.combine(new_start.date(), end_time))
        lesson.lesson_type = lesson_type
        lesson.save(update_fields=["lesson_type", "updated_at"])
        LessonService.reschedule_lesson(lesson, new_start, new_end, (request.POST.get("reason") or "").strip(), request.user)
    except Exception as exc:
        lesson = Lesson.objects.select_related("group", "group__course", "teacher", "course").get(id=lesson.id)
        return render(request, "crm/partials/schedule_lesson_drawer.html", {**get_schedule_context(request, selected_lesson=lesson, error=str(exc)), **get_lesson_attendance_context(request, lesson)}, status=400)

    lesson = Lesson.objects.select_related("group", "group__course", "teacher", "course").get(id=lesson.id)
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
    from schedule.services import LessonService, get_lesson_end_time
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
        group = get_object_or_404(SchoolGroups, id=group_id) if group_id else None
        selected_students = list(CustomUser.objects.filter(id__in=request.POST.getlist("students"), role=UserRole.STUDENT)) if group else []
        if not group:
            selected_students = [get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)]
        if lesson_type == Schedule.LESSON_TYPE_REGULAR:
            lesson_type = Lesson.LessonType.GROUP if group else Lesson.LessonType.INDIVIDUAL
        elif lesson_type == Schedule.LESSON_TYPE_SINGLE:
            lesson_type = Lesson.LessonType.SINGLE_GROUP if group else Lesson.LessonType.SINGLE_INDIVIDUAL
        end_time = get_lesson_end_time(classdate_start.time(), lessons_count)
        classdate_end = timezone.make_aware(datetime.combine(classdate_start.date(), end_time))
        lesson = LessonService.create_lesson(
            lesson_type=lesson_type,
            starts_at=classdate_start,
            ends_at=classdate_end,
            teacher=teacher,
            course=group.course if group else course,
            group=group,
            participants=selected_students,
            created_by=request.user,
        )
        if lesson.is_single:
            from sales.services import OrderService
            amount = request.POST.get("single_lesson_amount") or ""
            paid = request.POST.get("single_lesson_paid") in ["on", "true", "1"]
            payment_method = request.POST.get("single_lesson_payment_method") or "cash"
            order_student = None if lesson.group_id else selected_students[0]
            if not amount:
                raise ValueError("Укажите стоимость разового занятия")
            order = OrderService.create_single_lesson_order(
                lesson=lesson,
                student=order_student,
                amount=amount,
                payment_method=payment_method,
                paid=paid,
                created_by=request.user,
                comment="Продажа разового занятия из CRM",
            )
            item = order.items.first()
            if item:
                lesson.participants.update(order_item=item)
    except Exception as exc:
        return render(request, "crm/partials/schedule_create_lesson_drawer.html", get_create_lesson_context(request, error=str(exc)), status=400)

    response = HttpResponse(
        render_to_string("crm/partials/schedule_create_lesson_drawer.html", get_create_lesson_context(request), request=request)
        + render_to_string("crm/partials/schedule_lessons.html", {**get_schedule_context(request), "lessons_oob": True}, request=request)
    )
    response["HX-Trigger"] = hx_trigger(toast=crm_toast("Занятие создано"))
    return response


def schedule_attendance_mark_partial(request, lesson_id, student_id):
    from schedule.services import LessonService
    lesson = get_object_or_404(Lesson.objects.select_related("group", "group__course", "course"), id=lesson_id)
    student = get_object_or_404(CustomUser, id=student_id, role=UserRole.STUDENT)
    try:
        status_value = request.POST.get("status")
        lessons_count = int(request.POST.get("lessons_count") or 2)
        if status_value == "absent":
            status_value = LessonParticipant.AttendanceStatus.ABSENT_NOT_CHARGED
        participant, _ = LessonParticipant.objects.get_or_create(lesson=lesson, student=student)
        if participant.attendance_status != LessonParticipant.AttendanceStatus.PLANNED:
            raise ValueError("Посещение уже отмечено для этого ученика")
        LessonService.mark_participant_attendance(participant, status_value, lessons_count, request.user)
        student.update_active_status()
    except Exception as exc:
        return render(request, "crm/partials/schedule_attendance.html", get_lesson_attendance_context(request, lesson, error=str(exc)), status=400)
    return render(request, "crm/partials/schedule_attendance.html", get_lesson_attendance_context(request, lesson, success="Посещение успешно отмечено"))


def schedule_attendance_cancel_partial(request, attendance_id):
    from schedule.services import LessonService
    attendance = get_object_or_404(LessonParticipant.objects.select_related("lesson", "subscription", "student"), id=attendance_id)
    lesson = attendance.lesson
    student = attendance.student
    LessonService.cancel_participant_attendance(attendance, request.user)
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
