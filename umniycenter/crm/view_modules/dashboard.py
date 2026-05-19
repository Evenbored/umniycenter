from .common import *


def dashboard(request):
    selected_date = request.GET.get("date")
    dashboard = build_dashboard_payload(parse_dashboard_date(selected_date) if selected_date else None)
    context = {
        "dashboard": dashboard,
    }

    if request.headers.get("HX-Request") == "true":
        return render(request, "crm/partials/dashboard_content.html", context)

    return render(request, "crm/dashboard.html", context)
