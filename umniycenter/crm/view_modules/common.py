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
from accounts.api.serializers import ParentListSerializer, ParentUpdateSerializer
from courses.models import Courses
from groups.models import SchoolGroups
from main.models import ParticipantRequest
from students.api.views import create_student_with_parent, generate_parent_username, validate_optional_email, validate_optional_phone, validate_source
from students.models import StudentGroups
from students.api.serializers import StudentUpdateSerializer
from subscriptions.models import Payment, Subscription, Tariff
from subscriptions.payment_service import PaymentService
from subscriptions.api.serializers import PaymentSerializer
from schedule.models import Lesson, LessonParticipant, Schedule
from schedule.models import GroupScheduleTemplate
from communication.models import Message, Ticket, TicketStatus
from sales.models import Lead, LeadStatus, Order
from tasks.models import Task, TaskPriority, TaskStatus, TaskType
from tasks.services import TaskService
from crm.api.views import build_dashboard_payload, parse_dashboard_date

logger = logging.getLogger(__name__)

CRM_LIST_PAGE_SIZE = 50


def get_pagination(request, queryset, page_size=CRM_LIST_PAGE_SIZE):
    try:
        offset = max(int(request.GET.get("offset") or 0), 0)
    except (TypeError, ValueError):
        offset = 0
    if hasattr(queryset, "count"):
        try:
            total = queryset.count()
        except TypeError:
            total = len(queryset)
    else:
        total = len(queryset)

    try:
        items = list(queryset[offset:offset + page_size])
    except TypeError:
        items = list(queryset)[offset:offset + page_size]
    next_offset = offset + len(items)
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "next_offset": next_offset,
        "has_more": total > next_offset,
        "page_size": page_size,
        "is_load_more": offset > 0,
    }

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


def protect_crm_views(namespace, *view_names):
    for view_name in view_names:
        namespace[view_name] = login_required(admin_required(namespace[view_name]))
    return namespace
