import requests

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.models import UserRole
from crm.api_views import parse_dashboard_date

from .clients import AdminAIAssistant
from .context import build_dashboard_ai_context


def admin_required(view_func):
    def wrapped(request, *args, **kwargs):
        if request.user.role != UserRole.ADMIN and not request.user.is_staff:
            return render(
                request,
                "ai_assistant/partials/dashboard_insights.html",
                {"ai_error": "AI-помощник доступен только администратору."},
                status=403,
            )

        return view_func(request, *args, **kwargs)

    return wrapped


@login_required
@admin_required
@require_http_methods(["POST"])
def dashboard_insights(request):
    selected_date = parse_dashboard_date(request.POST.get("date"))
    context_text = build_dashboard_ai_context(selected_date)

    try:
        ai_insights = AdminAIAssistant().dashboard_insights(context_text)
        ai_error = ""
    except requests.Timeout:
        ai_insights = ""
        ai_error = "AI-помощник не ответил вовремя. Попробуйте ещё раз."
    except requests.ConnectionError:
        ai_insights = ""
        ai_error = "AI-помощник недоступен. Проверьте, запущен ли Ollama."
    except Exception:
        ai_insights = ""
        ai_error = "Не удалось сформировать AI-сводку. Проверьте настройки Ollama и модель."

    return render(
        request,
        "ai_assistant/partials/dashboard_insights.html",
        {
            "ai_insights": ai_insights,
            "ai_error": ai_error,
            "ai_context": context_text,
            "selected_date": selected_date,
        },
    )
