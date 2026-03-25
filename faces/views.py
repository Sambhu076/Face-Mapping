from io import BytesIO
import logging
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

try:
    import qrcode
except ImportError:  # pragma: no cover
    qrcode = None

from .forms import EventCreateForm, EventPhotoUploadForm, FaceSearchForm, StudioAuthenticationForm, StudioRegistrationForm
from .models import Event, FaceEmbedding, Photo
from .services import FaceServiceError, face_service

logger = logging.getLogger(__name__)
UPLOAD_BATCH_SIZE = 50


def _face_preview_data(photo: Photo, face: FaceEmbedding) -> dict:
    bbox = face.bounding_box or {}
    x1 = max(0, int(bbox.get("x1", 0)))
    y1 = max(0, int(bbox.get("y1", 0)))
    x2 = max(x1 + 1, int(bbox.get("x2", x1 + 1)))
    y2 = max(y1 + 1, int(bbox.get("y2", y1 + 1)))

    photo_width = max(photo.width, 1)
    photo_height = max(photo.height, 1)
    face_width = max(x2 - x1, 1)
    face_height = max(y2 - y1, 1)
    scale_x = 100.0 * photo_width / face_width
    scale_y = 100.0 * photo_height / face_height
    translate_x = -100.0 * x1 / face_width
    translate_y = -100.0 * y1 / face_height

    return {
        "id": face.id,
        "face_index": face.face_index,
        "person_id": face.person_id,
        "detection_score": face.detection_score,
        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        "preview_style": (
            f"--crop-scale-x:{scale_x:.4f}%;"
            f"--crop-scale-y:{scale_y:.4f}%;"
            f"--crop-translate-x:{translate_x:.4f}%;"
            f"--crop-translate-y:{translate_y:.4f}%;"
        ),
    }


def _annotate_admin_photo(photo: Photo) -> Photo:
    faces = list(photo.faces.order_by("face_index"))
    photo.detected_faces = [_face_preview_data(photo, face) for face in faces]
    return photo


def _redirect_target(request, default: str) -> str:
    return request.POST.get("next") or request.GET.get("next") or default


def _match_session_key(event_id: int) -> str:
    return f"last_match_ids_event_{event_id}"


def _match_payload_session_key(event_id: int) -> str:
    return f"last_match_payload_event_{event_id}"


def _load_session_matches(request, event_id: int):
    payload = request.session.get(_match_payload_session_key(event_id), [])
    if payload:
        score_by_photo = {
            item["photo_id"]: item.get("score", 0.0)
            for item in payload
            if isinstance(item, dict) and "photo_id" in item
        }
        match_ids = [photo_id for photo_id in score_by_photo]
    else:
        score_by_photo = {}
        match_ids = request.session.get(_match_session_key(event_id), [])
    if not match_ids:
        logger.info(
            "No session matches found for event_id=%s session_key=%s session_keys=%s",
            event_id,
            _match_session_key(event_id),
            list(request.session.keys()),
        )
        return []

    faces = (
        FaceEmbedding.objects.select_related("photo")
        .filter(photo_id__in=match_ids, photo__event_id=event_id)
        .order_by("photo_id", "face_index")
    )
    best_by_photo = {}
    for face in faces:
        if face.photo_id not in best_by_photo:
            best_by_photo[face.photo_id] = face

    matches = []
    for photo_id in match_ids:
        face = best_by_photo.get(photo_id)
        if face is None:
            logger.warning(
                "Session referenced photo_id=%s for event_id=%s but no FaceEmbedding row was found.",
                photo_id,
                event_id,
            )
            continue
        matches.append(
            {
                "face": face,
                "score": score_by_photo.get(photo_id, 0.0),
            }
        )
    logger.info(
        "Restored %s session matches for event_id=%s from %s stored photo ids.",
        len(matches),
        event_id,
        len(match_ids),
    )
    return matches


def landing_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("faces:home")
    return render(request, "faces/landing.html")


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("faces:admin-dashboard")
        if request.GET.get("force_admin") == "1":
            logout(request)
            messages.info(request, "Signed out of the guest session. Log in with an admin account.")
        else:
            return redirect("faces:landing")

    next_url = _redirect_target(request, "")
    form = StudioAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        if next_url:
            return redirect(next_url)
        if user.is_staff:
            return redirect("faces:admin-dashboard")
        return redirect("faces:landing")
    return render(request, "auth/login.html", {"form": form, "next_url": next_url})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("faces:home")

    next_url = _redirect_target(request, "")
    form = StudioRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data["first_name"]
        user.last_name = form.cleaned_data["last_name"]
        user.email = form.cleaned_data["email"]
        user.is_staff = False
        user.save()
        login(request, user)
        messages.success(request, "Account created. You can now access shared event links.")
        return redirect(next_url or "faces:home")
    return render(request, "auth/register.html", {"form": form, "next_url": next_url})


def logout_view(request):
    logout(request)
    return redirect("faces:login")


@login_required
def home(request):
    if request.user.is_staff:
        return redirect("faces:admin-dashboard")
    return redirect("faces:landing")


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "Only admin users can access the upload dashboard.")
        return redirect("faces:user-dashboard")

    event_form = EventCreateForm(prefix="event")
    rename_errors_event_id = None
    events = list(Event.objects.prefetch_related("photos").order_by("-created_at"))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create-event":
            event_form = EventCreateForm(request.POST, prefix="event")
            if event_form.is_valid():
                event = event_form.save()
                messages.success(request, f"Event created: {event.name}")
                return redirect("faces:admin-dashboard")
        elif action == "rename-event":
            event_id = request.POST.get("event_id")
            event = get_object_or_404(Event, id=event_id)
            rename_form = EventCreateForm(request.POST, prefix=f"rename-{event.id}", instance=event)
            if rename_form.is_valid():
                updated_event = rename_form.save()
                messages.success(request, f"Event updated: {updated_event.name}")
                return redirect("faces:admin-dashboard")
            rename_errors_event_id = event.id
        elif action == "delete-event":
            event_id = request.POST.get("event_id")
            event = get_object_or_404(Event, id=event_id)
            event_name = event.name
            event.delete()
            messages.success(request, f"Event deleted: {event_name}")
            return redirect("faces:admin-dashboard")

    total_faces = FaceEmbedding.objects.exclude(person_id="").values("person_id").distinct().count()
    recent_photos = Photo.objects.select_related("event").order_by("-uploaded_at")[:8]
    events = list(Event.objects.prefetch_related("photos").order_by("-created_at"))
    for event in events:
        event.uploaded_photos = list(event.photos.order_by("-uploaded_at"))
        if rename_errors_event_id == event.id:
            event.rename_form = rename_form
        else:
            event.rename_form = EventCreateForm(prefix=f"rename-{event.id}", instance=event)

    context = {
        "event_form": event_form,
        "photo_count": Photo.objects.count(),
        "face_count": total_faces,
        "recent_photos": recent_photos,
        "events": events,
    }
    return render(request, "faces/admin_dashboard.html", context)


@login_required
def admin_event_dashboard(request, event_id: int):
    if not request.user.is_staff:
        messages.error(request, "Only admin users can access the upload dashboard.")
        return redirect("faces:user-dashboard")

    event = get_object_or_404(Event, id=event_id)
    upload_form = EventPhotoUploadForm(prefix="upload")
    upload_summary = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "bulk-upload":
            upload_form = EventPhotoUploadForm(request.POST, request.FILES, prefix="upload")
            if upload_form.is_valid():
                files = upload_form.cleaned_data["photos"]
                success_count = 0
                failure_count = 0
                indexed_faces = 0
                errors: list[str] = []

                face_service.init_progress(event.id, len(files))

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
                        success_count += 1

                    from .tasks import process_photo_bulk_task
                    process_photo_bulk_task.delay(batch_photo_ids, event.id)

                upload_summary = {
                    "event": event,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "indexed_faces": "Processing in background",
                    "errors": errors,
                }
                if success_count:
                    messages.success(
                        request,
                        f"Queued {success_count} photo(s) for {event.name} to be indexed in the background.",
                    )
                if failure_count:
                    messages.warning(request, f"{failure_count} file(s) could not be indexed.")
        elif action == "delete-photo":
            photo_id = request.POST.get("photo_id")
            photo = get_object_or_404(Photo, id=photo_id, event=event)
            photo_title = photo.title or Path(photo.original_image.name).name
            face_service.delete_photo(photo)
            messages.success(request, f"Deleted photo: {photo_title}")
            return redirect("faces:admin-event-dashboard", event_id=event.id)
        elif action == "delete-all-photos":
            deleted_count = face_service.delete_event_photos(event.id)
            messages.success(request, f"Deleted {deleted_count} photo(s) from {event.name}.")
            return redirect("faces:admin-event-dashboard", event_id=event.id)

    total_faces = FaceEmbedding.objects.filter(photo__event=event).exclude(person_id="").values("person_id").distinct().count()
    photos = [
        _annotate_admin_photo(photo)
        for photo in event.photos.prefetch_related("faces").order_by("-uploaded_at")
    ]
    unique_faces = []
    seen_persons = set()
    for photo in photos:
        for face_data in getattr(photo, "detected_faces", []):
            person_id = face_data.get("person_id")
            if person_id and person_id not in seen_persons:
                seen_persons.add(person_id)
                face_copy = dict(face_data)
                face_copy["photo_url"] = photo.original_image.url
                unique_faces.append(face_copy)

    context = {
        "event": event,
        "upload_form": upload_form,
        "photo_count": event.photos.count(),
        "face_count": total_faces,
        "unique_faces": unique_faces,
        "photos": photos,
        "upload_summary": upload_summary,
        "shared_link": request.build_absolute_uri(event.access_path),
    }
    return render(request, "faces/event_admin_dashboard.html", context)


@login_required
def event_qr_code(request, event_id: int):
    if not request.user.is_staff:
        raise Http404("QR code not found.")

    event = Event.objects.filter(id=event_id).first()
    if event is None:
        raise Http404("Event not found.")
    if qrcode is None:
        return HttpResponse("QR generation library is not installed.", status=503, content_type="text/plain")

    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(request.build_absolute_uri(event.access_path))
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    if request.GET.get("download") == "1":
        response["Content-Disposition"] = f'attachment; filename="{event.slug}-qr.png"'
    return response


def user_dashboard(request):
    return render(
        request,
        "faces/user_dashboard.html",
        {
            "event": None,
            "matches": None,
            "search_form": None,
            "photo_count": 0,
            "face_count": 0,
        },
    )


def legacy_event_dashboard(request, access_key):
    event = Event.objects.filter(access_key=access_key).first()
    if event is None:
        raise Http404("Event not found.")
    return redirect("faces:event-user-dashboard", slug=event.ensure_slug(), access_key=event.access_key)


def event_dashboard(request, slug: str, access_key):
    event = Event.objects.filter(slug=slug, access_key=access_key).first()
    if event is None:
        raise Http404("Event not found.")

    search_form = FaceSearchForm(prefix="search")
    matches = None

    if request.method == "POST" and request.POST.get("action") == "search":
        search_form = FaceSearchForm(request.POST, request.FILES, prefix="search")
        logger.info(
            "Received face search POST for event_id=%s slug=%s has_file=%s session_key=%s",
            event.id,
            slug,
            "search-query_image" in request.FILES,
            request.session.session_key,
        )
        if search_form.is_valid():
            username = search_form.cleaned_data["username"]
            query_file = search_form.cleaned_data["query_image"]
            try:
                query_path = face_service.save_temp_query(query_file)
                matches = face_service.search(query_path, event_id=event.id)
                request.session[_match_session_key(event.id)] = [match.face.photo_id for match in matches]
                request.session[_match_payload_session_key(event.id)] = [
                    {"photo_id": match.face.photo_id, "score": float(match.score)}
                    for match in matches
                ]
                request.session["active_event_id"] = event.id
                request.session["active_search_username"] = username
                request.session.modified = True
                logger.info(
                    "Stored search results in session for event_id=%s username=%s match_count=%s first_photo_ids=%s session_key=%s",
                    event.id,
                    username,
                    len(matches),
                    [match.face.photo_id for match in matches[:10]],
                    request.session.session_key,
                )
                if matches == []:
                    logger.warning("No matches returned for event_id=%s username=%s query_file=%s", event.id, username, query_file.name)
                    messages.warning(request, f"No matching faces were found in {event.name}.")
            except FaceServiceError as exc:
                logger.warning(
                    "Face search failed for event_id=%s username=%s query_file=%s reason=%s",
                    event.id,
                    username,
                    query_file.name,
                    exc,
                )
                messages.error(request, str(exc))
        else:
            logger.warning(
                "Face search form invalid for event_id=%s errors=%s session_key=%s",
                event.id,
                search_form.errors.as_json(),
                request.session.session_key,
            )
    elif request.session.get("active_event_id") == event.id:
        logger.info(
            "Loading prior session matches for event_id=%s session_key=%s",
            event.id,
            request.session.session_key,
        )
        matches = _load_session_matches(request, event.id)

    total_faces = FaceEmbedding.objects.filter(photo__event=event).exclude(person_id="").values("person_id").distinct().count()
    context = {
        "search_form": search_form,
        "matches": matches,
        "event": event,
        "photo_count": event.photos.count(),
        "face_count": total_faces,
        "shared_link": request.build_absolute_uri(event.access_path),
        "search_username": request.session.get("active_search_username", ""),
    }
    return render(request, "faces/user_dashboard.html", context)


def download_photo(request, photo_id: int):
    photo = Photo.objects.select_related("event").filter(id=photo_id).first()
    if photo is None:
        raise Http404("Photo not found.")
    if not request.user.is_authenticated or not request.user.is_staff:
        event_id = request.session.get("active_event_id")
        allowed_ids = request.session.get(_match_session_key(event_id), []) if event_id else []
        logger.info(
            "Download photo requested photo_id=%s photo_event_id=%s session_event_id=%s allowed_count=%s session_key=%s",
            photo_id,
            photo.event_id,
            event_id,
            len(allowed_ids),
            request.session.session_key,
        )
        if photo.event_id != event_id or photo_id not in allowed_ids:
            logger.warning(
                "Blocked photo download for photo_id=%s photo_event_id=%s session_event_id=%s allowed=%s",
                photo_id,
                photo.event_id,
                event_id,
                photo_id in allowed_ids,
            )
            messages.error(request, "You can only download photos from the latest matched results for this event.")
            if photo.event_id:
                return redirect("faces:event-user-dashboard", slug=photo.event.slug, access_key=photo.event.access_key)
            return redirect("faces:landing")

    filename = Path(photo.original_image.name).name
    logger.info(
        "Serving photo download photo_id=%s path=%s exists=%s",
        photo_id,
        photo.original_image.path,
        Path(photo.original_image.path).exists(),
    )
    return FileResponse(photo.original_image.open("rb"), as_attachment=True, filename=filename)


def download_matched_photos(request):
    event_id = request.session.get("active_event_id")
    match_ids = request.session.get(_match_session_key(event_id), []) if event_id else []
    logger.info(
        "ZIP download requested session_event_id=%s match_count=%s session_key=%s",
        event_id,
        len(match_ids),
        request.session.session_key,
    )
    photos_by_id = Photo.objects.in_bulk(match_ids)
    photos = [photos_by_id[photo_id] for photo_id in match_ids if photo_id in photos_by_id]
    missing_ids = [photo_id for photo_id in match_ids if photo_id not in photos_by_id]
    if missing_ids:
        logger.warning(
            "ZIP download missing photo rows for event_id=%s missing_ids=%s",
            event_id,
            missing_ids[:20],
        )
    if not photos:
        logger.warning(
            "ZIP download found no photos for session_event_id=%s match_ids=%s",
            event_id,
            match_ids[:20],
        )
        messages.warning(request, "No matched photos are available for download yet.")
        if event_id:
            event = Event.objects.filter(id=event_id).first()
            if event:
                return redirect("faces:event-user-dashboard", slug=event.slug, access_key=event.access_key)
        return redirect("faces:landing")

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for photo in photos:
            filename = Path(photo.original_image.name).name
            file_exists = Path(photo.original_image.path).exists()
            logger.info(
                "Adding photo to ZIP photo_id=%s filename=%s exists=%s",
                photo.id,
                filename,
                file_exists,
            )
            with photo.original_image.open("rb") as source:
                archive.writestr(filename, source.read())

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    username = request.session.get("active_search_username", "guest")
    response["Content-Disposition"] = f'attachment; filename="{username}-matched-photos.zip"'
    logger.info(
        "Serving ZIP download username=%s event_id=%s photo_count=%s zip_bytes=%s",
        username,
        event_id,
        len(photos),
        len(buffer.getvalue()),
    )
    return response
