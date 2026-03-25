from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def frontend_app(request, *args, **kwargs):
    index_path = settings.BASE_DIR / "frontend_dist" / "index.html"
    if not index_path.exists():
        return HttpResponse(
            (
                "Frontend build not found. Run `npm.cmd install` and `npm.cmd run build` "
                "inside the `frontend` directory, or use `npm.cmd run dev` there during development."
            ),
            status=503,
            content_type="text/plain",
        )
    return HttpResponse(index_path.read_text(encoding="utf-8"))
