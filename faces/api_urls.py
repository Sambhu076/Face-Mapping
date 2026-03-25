from django.urls import path

from . import api_views


urlpatterns = [
    path("session/", api_views.session_view, name="api-session"),
    path("auth/login/", api_views.login_view, name="api-login"),
    path("auth/logout/", api_views.logout_view, name="api-logout"),
    path("admin/dashboard/", api_views.admin_dashboard_view, name="api-admin-dashboard"),
    path("admin/events/", api_views.create_event_view, name="api-create-event"),
    path("admin/events/<int:event_id>/", api_views.admin_event_view, name="api-admin-event"),
    path("admin/events/<int:event_id>/update/", api_views.update_event_view, name="api-update-event"),
    path("admin/events/<int:event_id>/delete/", api_views.delete_event_view, name="api-delete-event"),
    path("admin/events/<int:event_id>/upload/", api_views.upload_event_photos_view, name="api-upload-event-photos"),
    path("admin/events/<int:event_id>/cancel-tasks/", api_views.cancel_tasks_view, name="api-cancel-tasks"),
    path("admin/events/<int:event_id>/photos/<int:photo_id>/delete/", api_views.delete_photo_view, name="api-delete-photo"),
    path("admin/events/<int:event_id>/photos/delete-all/", api_views.delete_all_event_photos_view, name="api-delete-all-photos"),
    path("admin/events/<int:event_id>/indexing-progress/", api_views.indexing_progress_view, name="api-indexing-progress"),
    path("events/<slug:slug>/<uuid:access_key>/", api_views.public_event_view, name="api-public-event"),
    path("events/<slug:slug>/<uuid:access_key>/search/", api_views.public_event_search_view, name="api-public-event-search"),
]
