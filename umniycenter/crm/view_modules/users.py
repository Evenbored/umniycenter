from .common import *



def students_view(request):
    return render(request, "crm/students.html", get_students_context(request))



def teachers_view(request):
    return render(request, "crm/teachers.html", get_teachers_context(request))



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
    students_queryset = get_students_queryset(request)
    pagination = get_pagination(request, students_queryset)
    return {
        "students": pagination["items"],
        "students_count": pagination["total"],
        "next_offset": pagination["next_offset"],
        "has_more": pagination["has_more"],
        "is_load_more": pagination["is_load_more"],
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
    if course_id and selected_tariff and str(selected_tariff.course_id) != str(course_id):
        selected_tariff = None
        tariff_id = ""
    tariffs = Tariff.objects.select_related("course").filter(is_active=True)
    groups = SchoolGroups.objects.select_related("course", "teacher").filter(is_active=True)

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


def students_table_partial(request):
    return render(request, "crm/partials/students_table.html", get_students_context(request))


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


def student_buy_tariff_modal_partial(request, student_id):
    student = get_student_for_drawer(student_id)
    return render(request, "crm/partials/student_buy_tariff_modal.html", build_buy_tariff_context(request, student))


def student_payments_partial(request, student_id):
    student = get_student_for_drawer(student_id)
    return render(request, "crm/partials/student_payments.html", {"selected_student": student, "student_payments": get_student_payments(student)})


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


def teachers_table_partial(request):
    return render(request, "crm/partials/teachers_table.html", get_teachers_context(request))


def teacher_drawer_partial(request, teacher_id=None):
    teacher = get_teacher_for_drawer(teacher_id) if teacher_id else None
    return render(request, "crm/partials/teacher_drawer.html", get_teachers_context(request, selected_teacher=teacher))


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


def parents_table_partial(request):
    return render(request, "crm/partials/parents_table.html", get_parents_context(request))


def parent_drawer_partial(request, parent_id):
    parent = get_object_or_404(CustomUser.objects.prefetch_related(
        "parent_profile__students",
        "parent_profile__students__user",
    ), id=parent_id, role=UserRole.PARENT)
    return render(request, "crm/partials/parent_drawer.html", build_parent_drawer_context(request, parent=parent))


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


protect_crm_views(
    globals(),
    "students_view",
    "teachers_view",
    "parents_view",
    "students_table_partial",
    "student_drawer_partial",
    "student_save_partial",
    "student_add_group_partial",
    "student_remove_group_partial",
    "student_buy_tariff_modal_partial",
    "student_payments_partial",
    "student_subscription_freeze_partial",
    "student_subscription_unfreeze_partial",
    "student_confirm_payment_partial",
    "student_cancel_payment_partial",
    "student_buy_tariff_partial",
    "teachers_table_partial",
    "teacher_drawer_partial",
    "teacher_save_partial",
    "parents_table_partial",
    "parent_drawer_partial",
    "parent_save_partial",
)
