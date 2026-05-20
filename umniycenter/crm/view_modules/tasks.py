from .common import *


def tasks_view(request):
    return render(request, "crm/tasks.html", get_tasks_context(request))


def get_tasks_queryset(request):
    tasks = Task.objects.select_related("assignee", "author", "lead", "student", "parent", "payment", "subscription", "lesson", "ticket")
    search = (request.GET.get("search") or "").strip()
    status_filter = request.GET.get("status") or "active"
    assignee = request.GET.get("assignee") or ""
    task_type = request.GET.get("task_type") or ""
    priority = request.GET.get("priority") or ""
    today = timezone.now().date()

    if search:
        tasks = tasks.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(lead__child_fio__icontains=search) | Q(lead__parent_fio__icontains=search))
    if status_filter == "active":
        tasks = tasks.exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELED])
    elif status_filter == "overdue":
        tasks = tasks.exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELED]).filter(due_at__lt=timezone.now())
    elif status_filter == "today":
        tasks = tasks.exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELED]).filter(due_at__date=today)
    elif status_filter:
        tasks = tasks.filter(status=status_filter)
    if assignee == "me":
        tasks = tasks.filter(assignee=request.user)
    elif assignee:
        tasks = tasks.filter(assignee_id=assignee)
    if task_type:
        tasks = tasks.filter(task_type=task_type)
    if priority:
        tasks = tasks.filter(priority=priority)
    return tasks.order_by("status", "due_at", "-created_at")


def get_tasks_context(request, selected_task=None, error=None):
    qs = get_tasks_queryset(request)
    pagination = get_pagination(request, qs)
    tasks = pagination["items"]
    for task in tasks:
        task.crm_is_overdue = task.is_overdue
    if selected_task:
        selected_task.crm_is_overdue = selected_task.is_overdue
    active_qs = Task.objects.exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELED])
    return {
        "tasks": tasks,
        "tasks_count": pagination["total"],
        "next_offset": pagination["next_offset"],
        "has_more": pagination["has_more"],
        "is_load_more": pagination["is_load_more"],
        "new_count": Task.objects.filter(status=TaskStatus.NEW).count(),
        "today_count": active_qs.filter(due_at__date=timezone.now().date()).count(),
        "overdue_count": active_qs.filter(due_at__lt=timezone.now()).count(),
        "done_count": Task.objects.filter(status=TaskStatus.DONE).count(),
        "status_choices": TaskStatus.choices,
        "type_choices": TaskType.choices,
        "priority_choices": TaskPriority.choices,
        "admins": CustomUser.objects.filter(role=UserRole.ADMIN).order_by("last_name", "first_name"),
        "leads": Lead.objects.exclude(status__in=[LeadStatus.CONVERTED, LeadStatus.ARCHIVED]).order_by("-created_at")[:100],
        "selected_task": selected_task,
        "form_error": error,
    }


def get_task_for_drawer(task_id):
    return get_object_or_404(Task.objects.select_related("assignee", "author", "lead", "student", "parent", "payment", "subscription", "lesson", "ticket"), id=task_id)


def tasks_table_partial(request):
    return render(request, "crm/partials/tasks_table.html", get_tasks_context(request))


def task_drawer_partial(request, task_id=None):
    task = get_task_for_drawer(task_id) if task_id else None
    return render(request, "crm/partials/task_drawer.html", get_tasks_context(request, selected_task=task))


def task_oob_response(request, task, toast_message):
    drawer_html = render_to_string("crm/partials/task_drawer.html", get_tasks_context(request, selected_task=task), request=request)
    return render_oob_response("tasksTableHost", "crm/partials/tasks_table.html", get_tasks_context(request), request, drawer_html=drawer_html, triggers=hx_trigger("crm:refresh-stats", toast=crm_toast(toast_message)))


def task_save_partial(request, task_id=None):
    task = get_task_for_drawer(task_id) if task_id else None
    try:
        title = (request.POST.get("title") or "").strip()
        if not title:
            raise ValueError("Укажите название задачи")
        due_raw = request.POST.get("due_at") or ""
        due_at = None
        if due_raw:
            due_at = datetime.fromisoformat(due_raw)
            due_at = timezone.make_aware(due_at) if timezone.is_naive(due_at) else due_at
        assignee_id = request.POST.get("assignee") or ""
        lead_id = request.POST.get("lead") or ""
        payload = {
            "title": title,
            "description": (request.POST.get("description") or "").strip(),
            "task_type": request.POST.get("task_type") or TaskType.OTHER,
            "status": request.POST.get("status") or TaskStatus.NEW,
            "priority": request.POST.get("priority") or TaskPriority.MEDIUM,
            "assignee": CustomUser.objects.filter(id=assignee_id).first() if assignee_id else None,
            "lead": Lead.objects.filter(id=lead_id).first() if lead_id else None,
            "due_at": due_at,
        }
        if task is None:
            task = Task.objects.create(author=request.user, **payload)
        else:
            for field, value in payload.items():
                setattr(task, field, value)
            if task.status == TaskStatus.DONE and not task.completed_at:
                task.completed_at = timezone.now()
            task.save()
    except Exception as exc:
        return render(request, "crm/partials/task_drawer.html", get_tasks_context(request, selected_task=task, error=str(exc)), status=400)
    return task_oob_response(request, task, "Задача сохранена")


def task_complete_partial(request, task_id):
    task = get_task_for_drawer(task_id)
    task.complete()
    response = render(request, "crm/partials/tasks_table.html", get_tasks_context(request))
    response["HX-Trigger"] = hx_trigger("crm:refresh-stats", toast=crm_toast("Задача выполнена"))
    return response


protect_crm_views(
    globals(),
    "tasks_view",
    "tasks_table_partial",
    "task_drawer_partial",
    "task_save_partial",
    "task_complete_partial",
)
