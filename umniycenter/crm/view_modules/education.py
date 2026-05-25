from .common import *


def groups_view(request):
    return render(request, "crm/groups.html", get_groups_context(request))


def courses_view(request):
    return render(request, "crm/courses.html", get_courses_context(request))


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
    groups_queryset = get_groups_queryset(request)
    pagination = get_pagination(request, groups_queryset)
    return {
        "groups": pagination["items"],
        "groups_count": pagination["total"],
        "next_offset": pagination["next_offset"],
        "has_more": pagination["has_more"],
        "is_load_more": pagination["is_load_more"],
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


def groups_table_partial(request):
    return render(request, "crm/partials/groups_table.html", get_groups_context(request))


def groups_rows_partial(request):
    return render(request, "crm/partials/group_rows.html", get_groups_context(request))


def group_drawer_partial(request, group_id=None):
    group = get_group_for_drawer(group_id) if group_id else None
    return render(request, "crm/partials/group_drawer.html", get_groups_context(request, selected_group=group))


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


def group_template_delete_partial(request, group_id, template_id):
    group = get_group_for_drawer(group_id)
    try:
        GroupScheduleTemplate.objects.get(id=template_id, group=group).delete()
    except GroupScheduleTemplate.DoesNotExist:
        pass
    group = get_group_for_drawer(group_id)
    drawer_html = render_to_string("crm/partials/group_drawer.html", get_groups_context(request, selected_group=group), request=request)
    return render_oob_response("groupsTableHost", "crm/partials/groups_table.html", get_groups_context(request), request, drawer_html=drawer_html, triggers=hx_trigger(toast=crm_toast("Стандартное время удалено")))


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
    courses_queryset = get_courses_queryset(request)
    pagination = get_pagination(request, courses_queryset)
    return {
        "courses": pagination["items"],
        "courses_count": pagination["total"],
        "next_offset": pagination["next_offset"],
        "has_more": pagination["has_more"],
        "is_load_more": pagination["is_load_more"],
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


def courses_table_partial(request):
    return render(request, "crm/partials/courses_table.html", get_courses_context(request))


def courses_rows_partial(request):
    return render(request, "crm/partials/course_rows.html", get_courses_context(request))


def course_drawer_partial(request, course_id=None):
    course = get_object_or_404(Courses, id=course_id) if course_id else None
    return render(request, "crm/partials/course_drawer.html", build_course_drawer_context(request, course=course))


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


protect_crm_views(
    globals(),
    "groups_view",
    "courses_view",
    "groups_table_partial",
    "group_drawer_partial",
    "group_save_partial",
    "group_template_save_partial",
    "group_template_delete_partial",
    "courses_table_partial",
    "course_drawer_partial",
    "course_save_partial",
    "course_delete_partial",
)
