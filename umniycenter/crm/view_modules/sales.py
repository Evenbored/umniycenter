from .common import *


def requests_view(request):
    return render(request, "crm/requests.html", get_requests_context(request))


def leads_view(request):
    return render(request, "crm/leads.html", get_leads_context(request))


def build_lead_form_context(request, lead=None, error=None):
    return {
        **get_leads_context(request, selected_lead=lead, error=error),
        "courses": Courses.objects.all().order_by("name"),
        "student_form": build_student_from_lead_context(request, lead=lead)["student_form"] if lead else None,
    }


def get_requests_queryset(request):
    requests = ParticipantRequest.objects.prefetch_related("courses")
    search = (request.GET.get("search") or "").strip()
    status = request.GET.get("status") or "new"
    lead_status = request.GET.get("lead_status") or ""
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
    if lead_status:
        requests = requests.filter(lead__status=lead_status)

    if sort == "created":
        requests = requests.order_by("created")
    elif sort == "child_fio":
        requests = requests.order_by("child_fio", "-created")
    else:
        requests = requests.order_by("-created")

    return requests


def get_requests_context(request, selected_request=None, error=None):
    for participant_request in ParticipantRequest.objects.prefetch_related("courses").filter(lead__isnull=True)[:50]:
        Lead.from_participant_request(participant_request)
    requests_queryset = get_requests_queryset(request)
    pagination = get_pagination(request, requests_queryset)
    requests = pagination["items"]
    for participant_request in requests:
        try:
            participant_request.crm_lead = participant_request.lead
        except Lead.DoesNotExist:
            participant_request.crm_lead = None
    return {
        "participant_requests": requests,
        "requests_count": pagination["total"],
        "next_offset": pagination["next_offset"],
        "has_more": pagination["has_more"],
        "is_load_more": pagination["is_load_more"],
        "lead_new_count": Lead.objects.filter(status=LeadStatus.NEW).count(),
        "lead_work_count": Lead.objects.filter(status__in=[LeadStatus.IN_PROGRESS, LeadStatus.NO_ANSWER, LeadStatus.CONTACTED, LeadStatus.TRIAL_SCHEDULED, LeadStatus.TRIAL_COMPLETED, LeadStatus.WAITING_DECISION]).count(),
        "lead_converted_count": Lead.objects.filter(status=LeadStatus.CONVERTED).count(),
        "lead_lost_count": Lead.objects.filter(status=LeadStatus.LOST).count(),
        "lead_status_choices": LeadStatus.choices,
        "admins": CustomUser.objects.filter(role=UserRole.ADMIN).order_by("last_name", "first_name"),
        "selected_request": selected_request,
        "form_error": error,
    }


LEADS_COLUMN_PAGE_SIZE = 20


def get_leads_queryset(request, force_status=None, apply_status_filter=True):
    leads = Lead.objects.select_related(
        "participant_request",
        "assigned_to",
        "converted_student",
        "converted_parent",
    ).prefetch_related("courses")
    search = (request.GET.get("search") or "").strip()
    status_filter = request.GET.get("status") or ""
    assigned_to = request.GET.get("assigned_to") or ""
    source = request.GET.get("source") or ""
    sort = request.GET.get("sort") or "next_contact"

    if search:
        leads = leads.filter(
            Q(child_fio__icontains=search)
            | Q(parent_fio__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(courses__name__icontains=search)
            | Q(comment__icontains=search)
        ).distinct()
    if force_status:
        leads = leads.filter(status=force_status)
    elif apply_status_filter and status_filter:
        leads = leads.filter(status=status_filter)
    if assigned_to:
        leads = leads.filter(assigned_to_id=assigned_to)
    if source:
        leads = leads.filter(source=source)

    if sort == "created_old":
        leads = leads.order_by("created_at")
    elif sort == "updated_new":
        leads = leads.order_by("-updated_at")
    elif sort == "name_az":
        leads = leads.order_by("child_fio", "-created_at")
    else:
        leads = leads.order_by("next_contact_at", "-created_at")
    return leads


def get_leads_context(request, selected_lead=None, error=None):
    now = timezone.now()
    if selected_lead:
        selected_lead.is_contact_overdue = bool(selected_lead.next_contact_at and selected_lead.next_contact_at < now and selected_lead.status not in [LeadStatus.CONVERTED, LeadStatus.LOST, LeadStatus.ARCHIVED])

    selected_status = request.GET.get("status") or ""
    grouped_leads = {status: [] for status, _ in LeadStatus.choices}
    grouped_counts = {status: 0 for status, _ in LeadStatus.choices}
    grouped_has_more = {status: False for status, _ in LeadStatus.choices}

    for status, _ in LeadStatus.choices:
        if selected_status and selected_status != status:
            continue
        status_qs = get_leads_queryset(request, force_status=status, apply_status_filter=False)
        grouped_counts[status] = status_qs.count()
        grouped_has_more[status] = grouped_counts[status] > LEADS_COLUMN_PAGE_SIZE
        status_leads = list(status_qs[:LEADS_COLUMN_PAGE_SIZE])
        for lead in status_leads:
            lead.is_contact_overdue = bool(lead.next_contact_at and lead.next_contact_at < now and lead.status not in [LeadStatus.CONVERTED, LeadStatus.LOST, LeadStatus.ARCHIVED])
        grouped_leads[status] = status_leads

    work_statuses = [LeadStatus.IN_PROGRESS, LeadStatus.NO_ANSWER, LeadStatus.CONTACTED, LeadStatus.TRIAL_SCHEDULED, LeadStatus.TRIAL_COMPLETED, LeadStatus.WAITING_DECISION]
    total_count = get_leads_queryset(request).count()
    return {
        "leads": [],
        "grouped_leads": grouped_leads,
        "grouped_counts": grouped_counts,
        "grouped_has_more": grouped_has_more,
        "leads_count": total_count,
        "leads_page_size": LEADS_COLUMN_PAGE_SIZE,
        "lead_status_choices": LeadStatus.choices,
        "lead_new_count": Lead.objects.filter(status=LeadStatus.NEW).count(),
        "lead_work_count": Lead.objects.filter(status__in=work_statuses).count(),
        "lead_converted_count": Lead.objects.filter(status=LeadStatus.CONVERTED).count(),
        "lead_lost_count": Lead.objects.filter(status=LeadStatus.LOST).count(),
        "admins": CustomUser.objects.filter(role=UserRole.ADMIN).order_by("last_name", "first_name"),
        "source_choices": LeadSource.choices,
        "selected_lead": selected_lead,
        "form_error": error,
    }


def get_lead_for_drawer(lead_id):
    return get_object_or_404(
        Lead.objects.select_related("participant_request", "assigned_to", "converted_student", "converted_parent").prefetch_related("courses"),
        id=lead_id,
    )


def get_lead_cards_context(request, status_value, offset=0):
    now = timezone.now()
    qs = get_leads_queryset(request, force_status=status_value, apply_status_filter=False)
    total = qs.count()
    leads = list(qs[offset:offset + LEADS_COLUMN_PAGE_SIZE])
    for lead in leads:
        lead.is_contact_overdue = bool(lead.next_contact_at and lead.next_contact_at < now and lead.status not in [LeadStatus.CONVERTED, LeadStatus.LOST, LeadStatus.ARCHIVED])
    return {
        "status_value": status_value,
        "leads": leads,
        "next_offset": offset + len(leads),
        "has_more": total > offset + len(leads),
    }


def build_request_drawer_context(request, participant_request=None, error=None):
    lead = None
    if participant_request:
        lead = Lead.from_participant_request(participant_request)
    return {
        **get_requests_context(request, selected_request=participant_request, error=error),
        "selected_lead": lead,
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


def build_student_from_lead_context(request, lead=None, data=None, error=None):
    data = data or {}
    child_name = split_name(lead.child_fio if lead else "")
    parent_name = split_name(lead.parent_fio if lead else "")

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
        "source": value("source", lead.source if lead else ""),
        "parent_last_name": value("parent_last_name", parent_name["last_name"]),
        "parent_first_name": value("parent_first_name", parent_name["first_name"]),
        "parent_phone": value("parent_phone", lead.phone if lead else ""),
        "parent_email": value("parent_email", lead.email if lead else ""),
        "username": value("username", make_username(lead.child_fio if lead else "student")),
        "password": value("password", f"student{lead.id}" if lead else "student123"),
    }
    return {
        "lead": lead,
        "participant_request": lead.participant_request if lead else None,
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


def requests_table_partial(request):
    return render(request, "crm/partials/requests_table.html", get_requests_context(request))


def leads_board_partial(request):
    return render(request, "crm/partials/leads_board.html", get_leads_context(request))


@login_required
@admin_required
def leads_cards_partial(request):
    status_value = request.GET.get("status") or LeadStatus.NEW
    if status_value not in LeadStatus.values:
        return HttpResponseForbidden("Некорректный статус лида")
    try:
        offset = int(request.GET.get("offset") or 0)
    except ValueError:
        offset = 0
    return render(request, "crm/partials/lead_cards.html", get_lead_cards_context(request, status_value, offset=offset))


def lead_drawer_partial(request, lead_id):
    lead = get_lead_for_drawer(lead_id)
    return render(request, "crm/partials/lead_drawer.html", get_leads_context(request, selected_lead=lead))


def lead_create_drawer_partial(request):
    return render(request, "crm/partials/lead_create_drawer.html", build_lead_form_context(request))


def lead_create_partial(request):
    try:
        lead = Lead.objects.create(
            parent_fio=(request.POST.get("parent_fio") or "").strip(),
            child_fio=(request.POST.get("child_fio") or "").strip(),
            phone=(request.POST.get("phone") or "").strip(),
            email=(request.POST.get("email") or "").strip() or None,
            age=(request.POST.get("age") or "").strip(),
            source=request.POST.get("source") or None,
            status=request.POST.get("lead_status") or LeadStatus.NEW,
            assigned_to=CustomUser.objects.filter(id=request.POST.get("assigned_to"), role=UserRole.ADMIN).first() or request.user,
            comment=(request.POST.get("comment") or "").strip(),
        )
        if not lead.parent_fio or not lead.child_fio or not lead.phone:
            raise ValueError("Укажите родителя, ребенка и телефон")
        lead.courses.set(Courses.objects.filter(id__in=request.POST.getlist("courses")))
        TaskService.create_for_lead(lead, assignee=lead.assigned_to, author=request.user)
    except Exception as exc:
        return render(request, "crm/partials/lead_create_drawer.html", build_lead_form_context(request, error=str(exc)), status=400)
    drawer_html = render_to_string("crm/partials/lead_create_drawer.html", build_lead_form_context(request), request=request)
    return render_oob_response("leadsBoardHost", "crm/partials/leads_board.html", get_leads_context(request), request, drawer_html=drawer_html, triggers=hx_trigger("crm:close-lead-create-drawer", "crm:refresh-stats", toast=crm_toast("Лид создан, задача на контакт добавлена")))


def lead_oob_response(request, lead, toast_message):
    lead = get_lead_for_drawer(lead.id)
    drawer_html = render_to_string("crm/partials/lead_drawer.html", get_leads_context(request, selected_lead=lead), request=request)
    return render_oob_response(
        "leadsBoardHost",
        "crm/partials/leads_board.html",
        get_leads_context(request),
        request,
        drawer_html=drawer_html,
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast(toast_message)),
    )


def lead_update_partial(request, lead_id):
    lead = get_lead_for_drawer(lead_id)
    try:
        status_value = request.POST.get("lead_status") or lead.status
        if status_value not in LeadStatus.values:
            raise ValueError("Некорректный статус лида")
        assigned_to_id = request.POST.get("assigned_to") or ""
        next_contact_raw = request.POST.get("next_contact_at") or ""
        lost_reason = (request.POST.get("lost_reason") or "").strip()
        if status_value == LeadStatus.LOST and not lost_reason:
            raise ValueError("Для отказа укажите причину")
        lead.status = status_value
        lead.assigned_to = CustomUser.objects.filter(id=assigned_to_id, role=UserRole.ADMIN).first() if assigned_to_id else None
        lead.comment = (request.POST.get("comment") or "").strip()
        lead.lost_reason = lost_reason
        if next_contact_raw:
            next_contact = datetime.fromisoformat(next_contact_raw)
            lead.next_contact_at = timezone.make_aware(next_contact) if timezone.is_naive(next_contact) else next_contact
        else:
            lead.next_contact_at = None
        if status_value in [LeadStatus.CONTACTED, LeadStatus.NO_ANSWER, LeadStatus.TRIAL_SCHEDULED, LeadStatus.TRIAL_COMPLETED, LeadStatus.WAITING_DECISION]:
            lead.last_contact_at = timezone.now()
        lead.save()
    except Exception as exc:
        return render(request, "crm/partials/lead_drawer.html", get_leads_context(request, selected_lead=lead, error=str(exc)), status=400)
    return lead_oob_response(request, lead, "Лид обновлен")


def lead_status_partial(request, lead_id):
    lead = get_lead_for_drawer(lead_id)
    try:
        status_value = request.POST.get("lead_status") or ""
        if status_value not in LeadStatus.values:
            raise ValueError("Некорректный статус лида")
        lost_reason = (request.POST.get("lost_reason") or "").strip()
        if status_value == LeadStatus.LOST and not lost_reason and not lead.lost_reason:
            raise ValueError("Для отказа укажите причину в карточке лида")
        lead.status = status_value
        if lost_reason:
            lead.lost_reason = lost_reason
        if not lead.assigned_to_id:
            lead.assigned_to = request.user
        if status_value in [LeadStatus.CONTACTED, LeadStatus.NO_ANSWER, LeadStatus.TRIAL_SCHEDULED, LeadStatus.TRIAL_COMPLETED, LeadStatus.WAITING_DECISION]:
            lead.last_contact_at = timezone.now()
        lead.save(update_fields=["status", "assigned_to", "last_contact_at", "lost_reason", "updated_at"])
        if status_value == LeadStatus.NEW:
            TaskService.create_for_lead(lead, assignee=lead.assigned_to or request.user, author=request.user)
    except Exception as exc:
        if request.headers.get("HX-Target") == "leadDrawerContent":
            return render(request, "crm/partials/lead_drawer.html", get_leads_context(request, selected_lead=lead, error=str(exc)), status=400)
        return render(request, "crm/partials/leads_board.html", {**get_leads_context(request), "form_error": str(exc)}, status=400)
    if request.headers.get("HX-Target") == "leadDrawerContent":
        response = render(request, "crm/partials/lead_drawer.html", get_leads_context(request, selected_lead=get_lead_for_drawer(lead.id)))
    else:
        response = render(request, "crm/partials/leads_board.html", get_leads_context(request))
    response["HX-Trigger"] = hx_trigger("crm:refresh-stats", toast=crm_toast("Статус лида изменен"))
    return response


def lead_create_student_partial(request, lead_id):
    lead = get_lead_for_drawer(lead_id)

    if request.method == "GET":
        return render(request, "crm/partials/request_student_drawer.html", build_student_from_lead_context(request, lead=lead))

    try:
        with transaction.atomic():
            result, error = create_student_with_parent(request.POST)
            if error:
                raise ValueError(error.get("error") or serializer_errors_to_text(error))

            if lead.participant_request_id:
                lead.participant_request.checked = True
                lead.participant_request.save(update_fields=["checked"])
            lead.mark_converted(student=result["student"], parent=result.get("parent"))
    except Exception as exc:
        return render(
            request,
            "crm/partials/request_student_drawer.html",
            build_student_from_lead_context(request, lead=lead, data=request.POST, error=str(exc)),
            status=400,
        )

    lead = get_lead_for_drawer(lead_id)
    student = result["student"]
    lead_drawer_html = render_to_string("crm/partials/lead_drawer.html", get_leads_context(request, selected_lead=lead), request=request)
    student_drawer_html = render_to_string("crm/partials/request_student_drawer.html", build_student_from_lead_context(request, lead=lead), request=request)
    toast_text = f"Ученик {student.last_name} {student.first_name} создан. Логин: {student.username}"
    return render_oob_response(
        "leadsBoardHost",
        "crm/partials/leads_board.html",
        get_leads_context(request),
        request,
        drawer_html=lead_drawer_html + student_drawer_html,
        triggers=hx_trigger(
            "crm:close-student-drawer",
            "crm:refresh-stats",
            toast=crm_toast(toast_text, title="Ученик создан"),
        ),
    )


def request_drawer_partial(request, request_id):
    participant_request = get_request_for_drawer(request_id)
    return render(request, "crm/partials/request_drawer.html", build_request_drawer_context(request, participant_request=participant_request))


def request_mark_processed_partial(request, request_id):
    participant_request = get_request_for_drawer(request_id)
    participant_request.checked = True
    participant_request.save(update_fields=["checked"])
    lead = Lead.from_participant_request(participant_request, assigned_to=request.user)
    if lead.status == LeadStatus.NEW:
        lead.status = LeadStatus.CONTACTED
    if not lead.assigned_to_id:
        lead.assigned_to = request.user
    lead.last_contact_at = timezone.now()
    lead.save(update_fields=["status", "assigned_to", "last_contact_at", "updated_at"])

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
            lead = Lead.from_participant_request(participant_request, assigned_to=request.user)
            lead.mark_converted(student=result["student"], parent=result.get("parent"))
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


def request_lead_update_partial(request, request_id):
    participant_request = get_request_for_drawer(request_id)
    lead = Lead.from_participant_request(participant_request, assigned_to=request.user)
    try:
        status_value = request.POST.get("lead_status") or lead.status
        if status_value not in LeadStatus.values:
            raise ValueError("Некорректный статус лида")
        assigned_to_id = request.POST.get("assigned_to") or ""
        next_contact_raw = request.POST.get("next_contact_at") or ""
        lead.status = status_value
        lead.assigned_to = CustomUser.objects.filter(id=assigned_to_id, role=UserRole.ADMIN).first() if assigned_to_id else None
        lead.comment = (request.POST.get("comment") or "").strip()
        lead.lost_reason = (request.POST.get("lost_reason") or "").strip()
        if next_contact_raw:
            next_contact = datetime.fromisoformat(next_contact_raw)
            lead.next_contact_at = timezone.make_aware(next_contact) if timezone.is_naive(next_contact) else next_contact
        else:
            lead.next_contact_at = None
        if status_value in [LeadStatus.CONTACTED, LeadStatus.NO_ANSWER, LeadStatus.TRIAL_SCHEDULED, LeadStatus.TRIAL_COMPLETED, LeadStatus.WAITING_DECISION]:
            lead.last_contact_at = timezone.now()
        lead.save()
    except Exception as exc:
        return render(request, "crm/partials/request_drawer.html", build_request_drawer_context(request, participant_request=participant_request, error=str(exc)), status=400)

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
        triggers=hx_trigger("crm:refresh-stats", toast=crm_toast("Данные лида обновлены")),
    )
