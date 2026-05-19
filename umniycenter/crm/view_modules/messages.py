from .common import *


def messages_view(request):
    return render(request, "crm/messages.html", get_messages_context(request))


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


def messages_tickets_partial(request):
    return render(request, "crm/partials/messages_sidebar.html", get_messages_context(request))


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
