import json
from pathlib import Path

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import EventCreateForm
from .models import Event, FaceEmbedding, Photo
from .services import FaceServiceError, face_service
from .views import (
    UPLOAD_BATCH_SIZE,
    _annotate_admin_photo,
    _load_session_matches,
    _match_payload_session_key,
    _match_session_key,
)


def _json_error(message: str, status: int = 400, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _event_payload(event: Event) -> dict:
    return {
        "id": event.id,
        "name": event.name,
        "slug": event.slug,
        "eventDate": event.event_date.isoformat() if event.event_date else None,
        "accessKey": str(event.access_key),
        "accessPath": event.access_path,
        "createdAt": event.created_at.isoformat(),
        "photoCount": event.photos.count(),
        "faceCount": FaceEmbedding.objects.filter(photo__event=event).exclude(person_id="").values("person_id").distinct().count(),
    }


def _photo_payload(photo: Photo) -> dict:
    return {
        "id": photo.id,
        "title": photo.title or "Untitled Photo",
        "eventId": photo.event_id,
        "eventName": photo.display_event_name,
        "imageUrl": photo.original_image.url,
        "uploadedAt": photo.uploaded_at.isoformat(),
        "faceCount": photo.face_count,
        "faces": getattr(photo, "detected_faces", []),
    }


def _match_payload(match: dict | object) -> dict:
    face = match["face"] if isinstance(match, dict) else match.face
    score = match["score"] if isinstance(match, dict) else match.score
    return {
        "photoId": face.photo_id,
        "title": face.photo.title or "Untitled Photo",
        "eventName": face.photo.display_event_name,
        "imageUrl": face.photo.original_image.url,
        "score": float(score),
        "downloadUrl": f"/downloads/photo/{face.photo_id}/",
    }


def _session_payload(request) -> dict:
    return {
        "authenticated": request.user.is_authenticated,
        "isStaff": bool(request.user.is_authenticated and request.user.is_staff),
        "user": {
            "username": request.user.username,
            "fullName": request.user.get_full_name() or request.user.username,
        }
        if request.user.is_authenticated
        else None,
    }


def _require_staff(request):
    if not request.user.is_authenticated:
        return _json_error("Authentication required.", status=401)
    if not request.user.is_staff:
        return _json_error("Admin access required.", status=403)
    return None


@ensure_csrf_cookie
@require_GET
def session_view(request):
    return JsonResponse({"ok": True, **_session_payload(request)})


@require_POST
def login_view(request):
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return _json_error("Invalid username or password.", status=400)
    login(request, user)
    return JsonResponse({"ok": True, **_session_payload(request)})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True, **_session_payload(request)})


@require_GET
def admin_dashboard_view(request):
    denied = _require_staff(request)
    if denied:
        return denied

    events = list(Event.objects.prefetch_related("photos").order_by("-created_at"))
    total_faces = FaceEmbedding.objects.exclude(person_id="").values("person_id").distinct().count()
    return JsonResponse(
        {
            "ok": True,
            "photoCount": Photo.objects.count(),
            "faceCount": total_faces,
            "events": [_event_payload(event) for event in events],
        }
    )


@require_POST
def create_event_view(request):
    denied = _require_staff(request)
    if denied:
        return denied

    form = EventCreateForm(request.POST, prefix="event")
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    event = form.save()
    return JsonResponse({"ok": True, "event": _event_payload(event)})


@require_POST
def update_event_view(request, event_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    event = Event.objects.filter(id=event_id).first()
    if event is None:
        raise Http404("Event not found.")
    form = EventCreateForm(request.POST, prefix=f"rename-{event.id}", instance=event)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    updated_event = form.save()
    return JsonResponse({"ok": True, "event": _event_payload(updated_event)})


@require_POST
def delete_event_view(request, event_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    event = Event.objects.filter(id=event_id).first()
    if event is None:
        raise Http404("Event not found.")
    event_name = event.name
    event.delete()
    return JsonResponse({"ok": True, "deletedEvent": {"id": event_id, "name": event_name}})


@require_GET
def admin_event_view(request, event_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    event = Event.objects.filter(id=event_id).first()
    if event is None:
        raise Http404("Event not found.")

    photos = [
        _annotate_admin_photo(photo)
        for photo in event.photos.prefetch_related("faces").order_by("-uploaded_at")
    ]
    total_faces = FaceEmbedding.objects.filter(photo__event=event).exclude(person_id="").values("person_id").distinct().count()
    unique_faces = []
    seen_persons = set()
    for photo in photos:
        for face_data in getattr(photo, "detected_faces", []):
            person_id = face_data.get("person_id")
            if person_id and person_id not in seen_persons:
                seen_persons.add(person_id)
                face_copy = dict(face_data)
                face_copy["imageUrl"] = photo.original_image.url
                unique_faces.append(face_copy)

    return JsonResponse(
        {
            "ok": True,
            "event": _event_payload(event),
            "sharedLink": request.build_absolute_uri(event.access_path),
            "photoCount": event.photos.count(),
            "faceCount": total_faces,
            "uniqueFaces": unique_faces,
            "photos": [_photo_payload(photo) for photo in photos],
            "qrImageUrl": f"/events/{event.id}/qr/",
            "qrDownloadUrl": f"/events/{event.id}/qr/?download=1",
        }
    )


@require_POST
def upload_event_photos_view(request, event_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    event = Event.objects.filter(id=event_id).first()
    if event is None:
        raise Http404("Event not found.")

    files = request.FILES.getlist("photos")
    if not files:
        return _json_error("Select at least one photo to upload.")

    success_count = 0
    failure_count = 0
    errors: list[str] = []

    face_service.init_progress(event_id, len(files))

    created_photos = []
    last_task_id = None
    for batch_start in range(0, len(files), UPLOAD_BATCH_SIZE):
        batch_files = files[batch_start:batch_start + UPLOAD_BATCH_SIZE]
        batch_photo_ids = []
        for uploaded_file in batch_files:
            photo = Photo.objects.create(
                title=Path(uploaded_file.name).stem,
                event=event,
                event_name=event.name,
                original_image=uploaded_file,
            )
            batch_photo_ids.append(photo.id)
            created_photos.append(_photo_payload(photo))
            success_count += 1

        from .tasks import process_photo_bulk_task
        task = process_photo_bulk_task.delay(batch_photo_ids, event.id)
        last_task_id = task.id

    return JsonResponse(
        {
            "ok": True,
            "summary": {
                "successCount": success_count,
                "failureCount": failure_count,
                "errors": errors,
            },
            "photos": created_photos,
            "taskId": last_task_id,
        }
    )


@require_POST
def cancel_tasks_view(request, event_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    task_ids = data.get("taskIds", [])
    if not task_ids:
        return JsonResponse({"ok": True})

    from celery import current_app

    for tid in task_ids:
        if tid:
            current_app.control.revoke(tid, terminate=True)

    return JsonResponse({"ok": True})


@require_POST
def delete_photo_view(request, event_id: int, photo_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    photo = Photo.objects.filter(id=photo_id, event_id=event_id).first()
    if photo is None:
        raise Http404("Photo not found.")
    title = photo.title or Path(photo.original_image.name).name
    face_service.delete_photo(photo)
    return JsonResponse({"ok": True, "deletedPhoto": {"id": photo_id, "title": title}})


@require_POST
def delete_all_event_photos_view(request, event_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    deleted_count = face_service.delete_event_photos(event_id)
    return JsonResponse({"ok": True, "deletedCount": deleted_count})


@require_GET
def public_event_view(request, slug: str, access_key):
    event = Event.objects.filter(slug=slug, access_key=access_key).first()
    if event is None:
        raise Http404("Event not found.")

    total_faces = FaceEmbedding.objects.filter(photo__event=event).exclude(person_id="").values("person_id").distinct().count()
    matches = []
    if request.session.get("active_event_id") == event.id:
        matches = _load_session_matches(request, event.id)

    return JsonResponse(
        {
            "ok": True,
            "event": _event_payload(event),
            "photoCount": event.photos.count(),
            "faceCount": total_faces,
            "matches": [_match_payload(match) for match in matches],
            "downloadZipUrl": "/downloads/matches/",
            "searchUsername": request.session.get("active_search_username", ""),
        }
    )


@require_POST
def public_event_search_view(request, slug: str, access_key):
    event = Event.objects.filter(slug=slug, access_key=access_key).first()
    if event is None:
        raise Http404("Event not found.")

    username = request.POST.get("username", "").strip()
    query_file = request.FILES.get("query_image")
    if not username:
        return _json_error("Username is required.")
    if query_file is None:
        return _json_error("Query image is required.")

    try:
        query_path = face_service.save_temp_query(query_file)
        matches = face_service.search(query_path, event_id=event.id)
    except FaceServiceError as exc:
        return _json_error(str(exc), status=400)

    request.session[_match_session_key(event.id)] = [match.face.photo_id for match in matches]
    request.session[_match_payload_session_key(event.id)] = [
        {"photo_id": match.face.photo_id, "score": float(match.score)}
        for match in matches
    ]
    request.session["active_event_id"] = event.id
    request.session["active_search_username"] = username
    request.session.modified = True

    return JsonResponse(
        {
            "ok": True,
            "matches": [_match_payload(match) for match in matches],
            "downloadZipUrl": "/downloads/matches/",
        }
    )

@require_GET
def indexing_progress_view(request, event_id: int):
    denied = _require_staff(request)
    if denied:
        return denied

    event = Event.objects.filter(id=event_id).first()
    if event is None:
        raise Http404("Event not found.")

    progress = face_service.get_progress(event_id)
    return JsonResponse(
        {
            "ok": True,
            "progress": progress
        }
    )
