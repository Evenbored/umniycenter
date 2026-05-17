from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from accounts.models import CustomUser, UserRole
from communication.models import Message, Ticket, TicketStatus
from main.models import ParticipantRequest
from schedule.models import Schedule
from subscriptions.models import LessonAttendance, Payment, Subscription


def _full_name(user):
    if not user:
        return "Не указано"
    return user.get_full_name() or user.username or f"Пользователь #{user.id}"


def _format_datetime(value):
    if not value:
        return "не указано"
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")


def _format_money(value):
    return f"{value or 0:,.0f}".replace(",", " ")


def build_dashboard_ai_context(selected_date=None):
    """Build a compact CRM context for the administrator AI assistant."""
    selected_date = selected_date or timezone.localdate()
    now = timezone.now()
    soon_date = selected_date + timedelta(days=7)

    new_requests = ParticipantRequest.objects.filter(checked=False).prefetch_related("courses").order_by("-created")
    today_lessons = (
        Schedule.objects.filter(classdateStart__date=selected_date)
        .select_related("group", "group__course", "course", "student", "teacher")
        .order_by("classdateStart")
    )
    today_attendances = LessonAttendance.objects.filter(schedule__classdateStart__date=selected_date)
    pending_payments = (
        Payment.objects.filter(status="pending")
        .select_related("subscription", "subscription__student", "subscription__tariff", "parent")
        .order_by("-created_at")
    )
    completed_payments = Payment.objects.filter(status="completed", paid_at__date=selected_date)
    unread_parent_messages = Message.objects.filter(sender__role=UserRole.PARENT, is_read=False)
    active_tickets = Ticket.objects.filter(status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS]).select_related("parent")
    low_lesson_subscriptions = (
        Subscription.objects.filter(status="active", end_date__gte=selected_date)
        .annotate(lessons_remaining=F("lessons_total") - F("lessons_used"))
        .filter(lessons_remaining__lte=2)
        .select_related("student", "tariff", "tariff__course")
        .order_by("lessons_remaining", "end_date")
    )
    expiring_subscriptions = (
        Subscription.objects.filter(status="active", end_date__gte=selected_date, end_date__lte=soon_date)
        .select_related("student", "tariff", "tariff__course")
        .order_by("end_date")
    )

    attendance_by_group = (
        LessonAttendance.objects.filter(schedule__classdateStart__date=selected_date, schedule__group__isnull=False)
        .values("schedule__group__course__name", "schedule__group__number")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="present")), absent=Count("id", filter=Q(status="absent")))
        .order_by("-absent", "schedule__group__course__name")[:5]
    )

    lines = [
        f"Дата анализа: {selected_date.strftime('%d.%m.%Y')}",
        "",
        "Общие показатели:",
        f"- новых необработанных заявок: {new_requests.count()}",
        f"- занятий на выбранную дату: {today_lessons.count()}",
        f"- посещений отмечено: {today_attendances.filter(status='present').count()}",
        f"- пропусков отмечено: {today_attendances.filter(status='absent').count()}",
        f"- платежей ожидает подтверждения: {pending_payments.count()}",
        f"- доход за выбранную дату: {_format_money(completed_payments.aggregate(total=Sum('amount'))['total'])} ₽",
        f"- непрочитанных сообщений от родителей: {unread_parent_messages.count()}",
        f"- активных обращений родителей: {active_tickets.count()}",
        f"- активных абонементов с остатком <= 2 занятий: {low_lesson_subscriptions.count()}",
        f"- абонементов, заканчивающихся до {soon_date.strftime('%d.%m.%Y')}: {expiring_subscriptions.count()}",
    ]

    lines.extend(["", "Ближайшие необработанные заявки:"])
    for request in new_requests[:5]:
        courses = request.get_courses_display() or "курс не указан"
        lines.append(
            f"- заявка #{request.id}: ребёнок {request.child_fio}, возраст {request.age}, курсы: {courses}, создана {_format_datetime(request.created)}"
        )
    if not new_requests.exists():
        lines.append("- нет необработанных заявок")

    lines.extend(["", "Занятия на выбранную дату:"])
    for lesson in today_lessons[:8]:
        title = lesson.title
        teacher = _full_name(lesson.teacher)
        status = getattr(lesson, "actual_status", lesson.status)
        lines.append(f"- {_format_datetime(lesson.classdateStart)}: {title}, преподаватель: {teacher}, статус: {status}")
    if not today_lessons.exists():
        lines.append("- занятий нет")

    lines.extend(["", "Группы с пропусками на выбранную дату:"])
    has_group_absences = False
    for row in attendance_by_group:
        if row["absent"]:
            has_group_absences = True
            group_name = f"{row['schedule__group__course__name']} - {row['schedule__group__number']}"
            lines.append(f"- {group_name}: всего {row['total']}, присутствовали {row['present']}, отсутствовали {row['absent']}")
    if not has_group_absences:
        lines.append("- заметных групповых пропусков нет")

    lines.extend(["", "Платежи в ожидании:"])
    for payment in pending_payments[:5]:
        student = _full_name(payment.subscription.student)
        tariff = payment.subscription.tariff.name if payment.subscription and payment.subscription.tariff else "тариф не указан"
        lines.append(f"- платёж #{payment.id}: {student}, {tariff}, сумма {_format_money(payment.amount)} ₽, создан {_format_datetime(payment.created_at)}")
    if not pending_payments.exists():
        lines.append("- ожидающих платежей нет")

    lines.extend(["", "Абонементы с малым остатком:"])
    for subscription in low_lesson_subscriptions[:7]:
        lines.append(
            f"- {_full_name(subscription.student)}: {subscription.tariff.name}, осталось {subscription.lessons_remaining} занятий, действует до {subscription.end_date.strftime('%d.%m.%Y')}"
        )
    if not low_lesson_subscriptions.exists():
        lines.append("- нет абонементов с остатком <= 2 занятий")

    lines.extend(["", "Активные обращения родителей:"])
    for ticket in active_tickets.order_by("-last_message_at", "-created_at")[:5]:
        parent = _full_name(ticket.parent)
        subject = ticket.subject or ticket.get_category_display()
        lines.append(f"- обращение #{ticket.id}: {parent}, тема: {subject}, статус: {ticket.get_status_display()}")
    if not active_tickets.exists():
        lines.append("- активных обращений нет")

    lines.extend([
        "",
        "Задача для AI:",
        "Сформируй краткую сводку, приоритетные действия, риски и рекомендации для администратора CRM.",
    ])

    return "\n".join(lines)
