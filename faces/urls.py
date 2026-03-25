from django.urls import path

from .views import (
    admin_dashboard,
    admin_event_dashboard,
    download_matched_photos,
    download_photo,
    event_qr_code,
    event_dashboard,
    home,
    landing_view,
    legacy_event_dashboard,
    login_view,
    logout_view,
    register_view,
    user_dashboard,
)
from .frontend_views import frontend_app

app_name = "faces"

urlpatterns = [
    path("", frontend_app, name="landing"),
    path("login/", frontend_app, name="login"),
    path("register/", frontend_app, name="register"),
    path("logout/", logout_view, name="logout"),
    path("dashboard/", frontend_app, name="home"),
    path("dashboard/admin/", frontend_app, name="admin-dashboard"),
    path("dashboard/admin/events/<int:event_id>/", frontend_app, name="admin-event-dashboard"),
    path("dashboard/user/", frontend_app, name="user-dashboard"),
    path("dashboard/user/events/<uuid:access_key>/", legacy_event_dashboard, name="legacy-event-user-dashboard"),
    path("dashboard/user/events/<slug:slug>/<uuid:access_key>/", frontend_app, name="event-user-dashboard"),
    path("events/<int:event_id>/qr/", event_qr_code, name="event-qr"),
    path("events/<slug:slug>/<uuid:access_key>/", frontend_app, name="event-dashboard"),
    path("downloads/photo/<int:photo_id>/", download_photo, name="download-photo"),
    path("downloads/matches/", download_matched_photos, name="download-matches"),
    path("admin/", frontend_app, name="admin-legacy"),
]
