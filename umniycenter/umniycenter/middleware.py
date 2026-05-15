from django.http import HttpResponseBadRequest


class ApiAjaxOnlyMiddleware:
    """Reject direct browser navigation to JSON API endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/v1/") and not self._is_frontend_api_request(request):
            return HttpResponseBadRequest("Bad request")

        return self.get_response(request)

    def _is_frontend_api_request(self, request):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return True

        accept = request.headers.get("Accept", "")
        content_type = request.headers.get("Content-Type", "")

        return "application/json" in accept or "application/json" in content_type
