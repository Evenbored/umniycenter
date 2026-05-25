from datetime import timedelta, datetime
from decimal import Decimal

from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from accounts.models import CustomUser, UserRole
from accounts.permissions import IsAdminRole, IsSuperUser
from groups.models import SchoolGroups
from schedule.models import Schedule
from main.models import ParticipantRequest
from students.models import StudentGroups
from subscriptions.models import Payment, Subscription, LessonAttendance
from communication.models import Message
from subscriptions.api.serializers import LessonAttendanceSerializer, PaymentSerializer, SubscriptionSerializer


def parse_dashboard_date(date_str=None):
    """Parse dashboard date parameter with a safe fallback to today."""
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return timezone.localdate()

    return timezone.localdate()


def format_dashboard_currency(amount):
    """Format monetary values for dashboard templates and API payloads."""
    amount = Decimal(amount or 0)
    return f"{amount:,.0f}".replace(",", " ")


def format_dashboard_date(date_value):
    """Format dates for Russian dashboard headings."""
    months = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    return f"{date_value.day} {months[date_value.month - 1]} {date_value.year}"


def get_completed_payments_for_dashboard_date(selected_date):
    """Return completed payments for dashboard day.

    New payments have paid_at filled, but older/imported completed payments in this
    project may have paid_at=NULL. For dashboard reporting we treat created_at as
    the effective payment date only when paid_at is missing.
    """
    return Payment.objects.filter(status="completed").filter(
        Q(paid_at__date=selected_date)
        | Q(paid_at__isnull=True, created_at__date=selected_date)
    )


def get_dashboard_payment_dates(month_date):
    """Return dates in the visible month that have completed payments."""
    first_day = month_date.replace(day=1)
    next_month = (first_day + timedelta(days=32)).replace(day=1)

    paid_dates = set(
        Payment.objects.filter(
            status="completed",
            paid_at__date__gte=first_day,
            paid_at__date__lt=next_month,
        )
        .values_list("paid_at__date", flat=True)
        .distinct()
    )
    created_dates_without_paid_at = set(
        Payment.objects.filter(
            status="completed",
            paid_at__isnull=True,
            created_at__date__gte=first_day,
            created_at__date__lt=next_month,
        )
        .values_list("created_at__date", flat=True)
        .distinct()
    )
    return paid_dates | created_dates_without_paid_at


def build_dashboard_calendar(selected_date, payment_dates=None):
    """Build a month calendar grid for the dashboard."""
    months = [
        "Январь",
        "Февраль",
        "Март",
        "Апрель",
        "Май",
        "Июнь",
        "Июль",
        "Август",
        "Сентябрь",
        "Октябрь",
        "Ноябрь",
        "Декабрь",
    ]

    payment_dates = payment_dates or set()
    first_day = selected_date.replace(day=1)
    grid_start = first_day - timedelta(days=first_day.weekday())
    today = timezone.localdate()
    weeks = []
    days = []

    for week_index in range(6):
        week = []
        for day_index in range(7):
            current_day = grid_start + timedelta(days=week_index * 7 + day_index)
            week.append(
                {
                    "date": current_day,
                    "date_iso": current_day.isoformat(),
                    "day": current_day.day,
                    "is_current_month": current_day.month == selected_date.month,
                    "is_today": current_day == today,
                    "is_selected": current_day == selected_date,
                    "has_payments": current_day in payment_dates,
                }
            )
            days.append(week[-1])
        weeks.append(week)

    prev_month = (first_day - timedelta(days=1)).replace(day=1)
    next_month = (first_day + timedelta(days=32)).replace(day=1)

    return {
        "month_label": f"{months[selected_date.month - 1]} {selected_date.year}",
        "selected_date_display": format_dashboard_date(selected_date),
        "selected_date_iso": selected_date.isoformat(),
        "prev_month_date": prev_month.isoformat(),
        "next_month_date": next_month.isoformat(),
        "weeks": weeks,
        "days": days,
        "weekdays": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    }


def build_dashboard_payload(selected_date=None):
    """Build the dashboard payload used by both HTML and API responses."""
    selected_date = selected_date or timezone.localdate()

    students_count = CustomUser.objects.filter(role=UserRole.STUDENT, is_active=True).count()
    parents_count = CustomUser.objects.filter(role=UserRole.PARENT).count()
    teachers_count = CustomUser.objects.filter(role=UserRole.TEACHER).count()
    groups_count = SchoolGroups.objects.filter(is_active=True).count()
    new_requests_count = ParticipantRequest.objects.filter(checked=False).count()
    payments_count = Payment.objects.count()
    unread_messages_count = Message.objects.filter(sender__role=UserRole.PARENT, is_read=False).count()

    payments_on_date = (
        get_completed_payments_for_dashboard_date(selected_date)
        .select_related(
            "subscription",
            "subscription__group",
            "subscription__tariff",
            "subscription__student",
        )
    )

    subscriptions_group = 0
    subscriptions_individual = 0
    subscriptions_new = 0
    subscriptions_renewal = 0

    def is_group_payment(payment):
        subscription = payment.subscription
        tariff = subscription.tariff
        if getattr(tariff, "subscription_type", None) == "group":
            return True
        if subscription.group_id:
            return True
        return StudentGroups.objects.filter(
            student=subscription.student,
            group__course=tariff.course,
        ).exists()

    def is_renewal_payment(payment):
        subscription = payment.subscription
        paid_at = payment.paid_at or payment.updated_at or payment.created_at
        if not paid_at:
            return False

        return Subscription.objects.filter(
            student=subscription.student,
            tariff__course=subscription.tariff.course,
            created_at__lt=paid_at,
        ).exclude(id=subscription.id).exists()

    for payment in payments_on_date:
        if is_group_payment(payment):
            subscriptions_group += 1
        else:
            subscriptions_individual += 1

        if is_renewal_payment(payment):
            subscriptions_renewal += 1
        else:
            subscriptions_new += 1

    attendances_on_date = (
        LessonAttendance.objects.filter(schedule__classdateStart__date=selected_date, status="present")
        .select_related("schedule", "schedule__group", "student")
    )

    attendance_group = 0
    attendance_individual = 0

    for attendance in attendances_on_date:
        if attendance.schedule.group_id:
            attendance_group += 1
        else:
            attendance_individual += 1

    income_breakdown = {
        "groupSubscriptions": Decimal("0"),
        "groupSingle": Decimal("0"),
        "individualSubscriptions": Decimal("0"),
        "individualSingle": Decimal("0"),
        "rentSubscriptions": Decimal("0"),
        "rentSingle": Decimal("0"),
        "products": Decimal("0"),
        "accountTopup": Decimal("0"),
    }

    for payment in payments_on_date:
        if is_group_payment(payment):
            income_breakdown["groupSubscriptions"] += Decimal(payment.amount)
        else:
            income_breakdown["individualSubscriptions"] += Decimal(payment.amount)

    total_income = sum(income_breakdown.values())
    max_income = max(income_breakdown.values()) if any(income_breakdown.values()) else Decimal("0")

    refunds_on_date = (
        Payment.objects.filter(status="refunded", updated_at__date=selected_date).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    expense_breakdown = {
        "accountWithdraw": Decimal("0"),
        "refunds": Decimal(refunds_on_date),
    }

    total_expense = sum(expense_breakdown.values())
    max_expense = max(expense_breakdown.values()) if any(expense_breakdown.values()) else Decimal("0")
    total_balance = total_income - total_expense

    group_attendances = []
    groups_with_lessons = (
        Schedule.objects.filter(classdateStart__date=selected_date, group__isnull=False)
        .select_related("group", "group__course")
        .distinct()
    )

    for schedule in groups_with_lessons:
        if schedule.group:
            attendances = LessonAttendance.objects.filter(schedule=schedule)
            present_count = attendances.filter(status="present").count()
            absent_count = attendances.filter(status="absent").count()
            total_count = attendances.count()

            if total_count > 0:
                group_attendances.append(
                    {
                        "group_name": f"{schedule.group.course.name} - {schedule.group.number}",
                        "total": total_count,
                        "present": present_count,
                        "absent": absent_count,
                    }
                )

    individual_attendances = []
    individual_lessons = (
        LessonAttendance.objects.filter(schedule__classdateStart__date=selected_date, schedule__group__isnull=True)
        .select_related("student", "schedule")
    )

    for attendance in individual_lessons:
        individual_attendances.append(
            {
                "student_name": attendance.student.get_full_name() or attendance.student.username,
                "status": attendance.status,
                "present": 1 if attendance.status == "present" else 0,
                "absent": 1 if attendance.status == "absent" else 0,
            }
        )

    return {
        "date": selected_date.isoformat(),
        "date_display": format_dashboard_date(selected_date),
        "calendar": build_dashboard_calendar(selected_date, get_dashboard_payment_dates(selected_date)),
        "stats": {
            "students_count": students_count,
            "parents_count": parents_count,
            "teachers_count": teachers_count,
            "groups_count": groups_count,
            "new_requests_count": new_requests_count,
            "payments_count": payments_count,
            "unread_messages_count": unread_messages_count,
        },
        "subscriptions": {
            "group": subscriptions_group,
            "individual": subscriptions_individual,
            "new": subscriptions_new,
            "renewal": subscriptions_renewal,
            "total": subscriptions_group + subscriptions_individual,
        },
        "singleLessons": {
            "group": 0,
            "individual": 0,
            "total": 0,
        },
        "products": {
            "total": 0,
        },
        "attendance": {
            "group": attendance_group,
            "individual": attendance_individual,
            "total": attendance_group + attendance_individual,
        },
        "balance": {
            "income": {
                "total": total_income,
                "breakdown": income_breakdown,
                "items": [
                    {
                        "key": "groupSubscriptions",
                        "label": "Групп. абонементы",
                        "amount": income_breakdown["groupSubscriptions"],
                        "formatted": format_dashboard_currency(income_breakdown["groupSubscriptions"]),
                        "percent": float((income_breakdown["groupSubscriptions"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "groupSingle",
                        "label": "Групп. разовые",
                        "amount": income_breakdown["groupSingle"],
                        "formatted": format_dashboard_currency(income_breakdown["groupSingle"]),
                        "percent": float((income_breakdown["groupSingle"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "individualSubscriptions",
                        "label": "Индив. абонементы",
                        "amount": income_breakdown["individualSubscriptions"],
                        "formatted": format_dashboard_currency(income_breakdown["individualSubscriptions"]),
                        "percent": float((income_breakdown["individualSubscriptions"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "individualSingle",
                        "label": "Индив. разовые",
                        "amount": income_breakdown["individualSingle"],
                        "formatted": format_dashboard_currency(income_breakdown["individualSingle"]),
                        "percent": float((income_breakdown["individualSingle"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "rentSubscriptions",
                        "label": "Абон. на аренду",
                        "amount": income_breakdown["rentSubscriptions"],
                        "formatted": format_dashboard_currency(income_breakdown["rentSubscriptions"]),
                        "percent": float((income_breakdown["rentSubscriptions"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "rentSingle",
                        "label": "Разовая аренда",
                        "amount": income_breakdown["rentSingle"],
                        "formatted": format_dashboard_currency(income_breakdown["rentSingle"]),
                        "percent": float((income_breakdown["rentSingle"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "products",
                        "label": "Продажа товаров",
                        "amount": income_breakdown["products"],
                        "formatted": format_dashboard_currency(income_breakdown["products"]),
                        "percent": float((income_breakdown["products"] / max_income * 100) if max_income else 0),
                    },
                    {
                        "key": "accountTopup",
                        "label": "Пополнение ЛС",
                        "amount": income_breakdown["accountTopup"],
                        "formatted": format_dashboard_currency(income_breakdown["accountTopup"]),
                        "percent": float((income_breakdown["accountTopup"] / max_income * 100) if max_income else 0),
                    },
                ],
            },
            "expense": {
                "total": total_expense,
                "breakdown": expense_breakdown,
                "items": [
                    {
                        "key": "accountWithdraw",
                        "label": "Вывод с ЛС",
                        "amount": expense_breakdown["accountWithdraw"],
                        "formatted": format_dashboard_currency(expense_breakdown["accountWithdraw"]),
                        "percent": float((expense_breakdown["accountWithdraw"] / max_expense * 100) if max_expense else 0),
                    },
                    {
                        "key": "refunds",
                        "label": "Возвраты",
                        "amount": expense_breakdown["refunds"],
                        "formatted": format_dashboard_currency(expense_breakdown["refunds"]),
                        "percent": float((expense_breakdown["refunds"] / max_expense * 100) if max_expense else 0),
                    },
                ],
            },
            "total": total_balance,
            "formatted_total": format_dashboard_currency(total_balance),
            "formatted_income_total": format_dashboard_currency(total_income),
            "formatted_expense_total": format_dashboard_currency(total_expense),
        },
        "groupAttendances": group_attendances,
        "individualAttendances": individual_attendances,
    }


class CrmDashboardAPIView(APIView):
    permission_classes = [IsAdminRole | IsSuperUser]

    def get(self, request):
        selected_date = parse_dashboard_date(request.GET.get("date"))
        return Response(build_dashboard_payload(selected_date))


@api_view(["GET"])
def student_account_history(request, student_id):
    """Сводная история ученика за весь период существования аккаунта."""
    if request.user.role not in [UserRole.ADMIN, UserRole.TEACHER]:
        return Response({"error": "Доступ запрещен"}, status=403)

    try:
        student = CustomUser.objects.get(id=student_id, role=UserRole.STUDENT)
    except CustomUser.DoesNotExist:
        return Response({"error": "Ученик не найден"}, status=404)

    if request.user.role == UserRole.TEACHER:
        has_access = StudentGroups.objects.filter(student=student, group__teacher=request.user).exists()
        if not has_access:
            return Response({"error": "Доступ запрещен"}, status=403)

    attendances = (
        LessonAttendance.objects
        .filter(student=student)
        .select_related("schedule", "schedule__group", "schedule__group__course", "subscription", "marked_by")
        .order_by("-schedule__classdateStart", "-created_at")
    )
    subscriptions = (
        Subscription.objects
        .filter(student=student)
        .select_related("student", "parent", "tariff", "tariff__course")
        .order_by("-created_at")
    )
    payments = (
        Payment.objects
        .filter(subscription__student=student)
        .select_related("subscription", "subscription__student", "subscription__tariff", "subscription__tariff__course", "parent")
        .order_by("-created_at")
    )

    full_name = student.get_full_name() or student.username
    name_parts = [part for part in full_name.split() if part]
    enrollment_q = Q(phone=student.phone) if student.phone else Q()
    if name_parts:
        child_name_q = Q()
        for part in name_parts:
            child_name_q &= Q(child_fio__icontains=part)
        enrollment_q |= child_name_q

    enrollments = []
    if name_parts or student.phone:
        for item in ParticipantRequest.objects.filter(enrollment_q).prefetch_related("courses").order_by("-created")[:20]:
            enrollments.append({
                "id": item.id,
                "parent_fio": item.parent_fio,
                "child_fio": item.child_fio,
                "phone": item.phone,
                "email": item.email or "",
                "age": item.age,
                "courses": [course.name for course in item.courses.all()],
                "source": item.get_source_display() if item.source else "",
                "created": item.created,
                "checked": item.checked,
            })

    return Response({
        "student": {
            "id": student.id,
            "name": full_name,
            "phone": student.phone or "",
            "date_joined": student.date_joined,
        },
        "visits": LessonAttendanceSerializer(attendances, many=True).data,
        "services": SubscriptionSerializer(subscriptions, many=True).data,
        "products": PaymentSerializer(payments, many=True).data,
        "enrollment": enrollments,
    })
