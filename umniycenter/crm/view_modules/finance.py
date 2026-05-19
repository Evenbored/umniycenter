from .common import *


def payments_view(request):
    return render(request, "crm/payments.html", get_payments_context(request))


def subscriptions_view(request):
    return render(request, "crm/subscriptions.html", get_subscriptions_context(request))


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


def subscriptions_table_partial(request):
    return render(request, "crm/partials/subscriptions_table.html", get_subscriptions_context(request))


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


def subscription_unfreeze_partial(request, subscription_id):
    try:
        subscription = get_subscription_for_drawer(subscription_id)
        subscription.unfreeze(created_by=request.user)
    except Exception as exc:
        subscription = get_subscription_for_drawer(subscription_id)
        return render(request, "crm/partials/subscription_drawer.html", get_subscriptions_context(request, subscription=subscription, error=str(exc)), status=400)
    return subscription_oob_response(request, subscription, "Абонемент разморожен")


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


def payments_table_partial(request):
    return render(request, "crm/partials/payments_table.html", get_payments_context(request))


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


def tariffs_table_partial(request):
    return render(request, "crm/partials/tariffs_table.html", get_tariffs_context(request))


def tariff_drawer_partial(request, tariff_id=None):
    tariff = get_object_or_404(Tariff, id=tariff_id) if tariff_id else None
    return render(request, "crm/partials/tariff_drawer.html", build_tariff_drawer_context(request, tariff=tariff))


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
