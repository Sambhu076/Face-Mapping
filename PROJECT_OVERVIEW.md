# Studio Face Finder - Project Overview

## 1. Introduction
Studio Face Finder is an event-focused face recognition platform for photography studios and organizers. Admin users create events, upload batches of event photos, and let the system detect, index, and group faces automatically. Guests then open an event-specific link or QR code, upload a selfie, and receive the photos from that event that best match their face.

The current codebase is centered on a Django application with server-rendered dashboards, PostgreSQL-backed metadata, Redis-assisted background processing, and FAISS-based vector search over InsightFace embeddings.

## 2. Current Stack

### Backend
- Django application in `studioface/` and `faces/`
- PostgreSQL as the default relational database in Docker
- Redis for caching and Celery broker/result backend
- Celery worker for asynchronous bulk photo indexing
- InsightFace (`buffalo_l`) for face detection and embedding generation
- OpenCV available for image loading and optional fallback detection
- FAISS for event-specific similarity search

### Frontend
- Server-rendered Django templates under `templates/`
- Shared CSS in `static/css/styles.css`
- Separate React/Vite frontend workspace in `frontend/`
- Prebuilt frontend assets served from `frontend_dist/` when present

### Deployment
- Docker and Docker Compose orchestrate `web`, `db`, `redis`, `celery_worker`, and `frontend`
- Persistent volumes store PostgreSQL data, uploaded media, and FAISS index data
- Environment-specific configuration is managed via `.env` (overriding default settings)

## 3. Core Domain Model
The main application data lives in `faces/models.py`.

### Event
- Stores the event name, generated slug, date, and a UUID `access_key`
- Provides an `access_path` used for guest dashboards and QR-based sharing
- Acts as the parent scope for uploaded photos and search results

### Photo
- Belongs to an `Event`
- Stores the uploaded original image, optional title, image dimensions, and detected face count
- Keeps event naming metadata and upload timestamps

### FaceEmbedding
- Represents one detected face inside one photo
- Stores bounding box coordinates, landmarks, detection score, and embedding vector
- Stores `person_id` so repeated appearances of the same person can be grouped across an event

## 4. Application Flow

### Admin workflow
1. Staff users sign in and open the admin dashboard.
2. They create an event.
3. They open the event dashboard and upload up to 20 files per form submission.
4. The app saves the `Photo` rows immediately and dispatches Celery tasks in batches.
5. Background workers detect faces, generate embeddings, assign or reuse `person_id` values, and update the event FAISS index.
6. Admins can review uploaded photos, inspect detected faces, and manage the archive with built-in **confirmation modals** for deleting individual photos, deleting all photos, or deleting entire events.
7. Admins share the event link or QR code with guests.

### Guest workflow
1. A guest opens `/dashboard/user/events/{slug}/{access_key}/`.
2. They upload a selfie through the event-specific dashboard.
3. The app extracts one or more query faces, ranks them, and searches the event-specific FAISS index.
4. Best matches are grouped by photo and stored in the Django session.
5. The guest can download matched photos individually or as a ZIP archive.

## 5. Face Recognition and Search
The face pipeline is implemented in `faces/services.py`.

- Images are loaded and resized before inference to reduce processing overhead.
- InsightFace `FaceAnalysis` is initialized with the configured providers and `det_size=(320, 320)`.
- Low-confidence detections are filtered using `FACE_DETECTION_CONFIDENCE_THRESHOLD`.
- Embeddings are L2-normalized before indexing and search.
- Each event gets its own FAISS files:
  - `data/{event_id}_face.index`
  - `data/{event_id}_face_mapping.json`
- The FAISS index uses `IndexHNSWFlat`, which is better aligned with approximate nearest-neighbor search than the older overview described.
- Search results are filtered by similarity threshold, deduplicated by photo, sorted by score, and capped by `MAX_RESULTS`.

## 6. Background Processing
Bulk indexing is handled asynchronously.

- `faces/tasks.py` defines `process_photo_bulk_task`
- The task calls `face_service.index_photos_bulk(...)`
- Processing includes parallel image loading, parallel inference, bulk creation of `FaceEmbedding` rows, and persistence of the updated FAISS index
- Redis cache keys track indexing progress per event so the UI can surface processing state

## 7. Access Control and Security

### Admin access
- Django-authenticated staff users manage events and uploads
- Admin-only views are protected with `@login_required` plus `request.user.is_staff` checks
- Django admin is exposed separately at `/django-admin/`

### Guest access
- Guest event dashboards are scoped by event `slug` and `access_key`
- Guests do not need staff access to search within a shared event
- Download permissions are constrained by session-stored match results so guests can only fetch photos from their latest matched event session

### Session behavior
- The app stores:
  - active event id
  - active search username
  - matched photo ids and scores
- ZIP downloads are generated only from those session-scoped matched photo ids

## 8. Configuration Highlights
Key runtime settings currently come from `.env` (primary) and `studioface/settings.py` (defaults).

- `FACE_SIMILARITY_THRESHOLD`: `0.60` (defaulted to `0.45` in code)
- `FACE_DETECTION_CONFIDENCE_THRESHOLD`: `0.60` (defaulted to `0.55` in code)
- `FACE_SEARCH_TOP_K`: `128` (defaulted to `256` in code)
- `MAX_RESULTS`: `24`
- `FACE_INSIGHTFACE_PROVIDERS`: defaults to `CPUExecutionProvider`
- `FACE_SEARCH_ALL_QUERY_FACES`: defaults to `true`
- `ALLOW_OPENCV_FALLBACK`: optional fallback when InsightFace is unavailable
- PostgreSQL is configured as the default database in settings and Compose
- Redis is configured for both Django caching and Celery

## 9. Project Structure
- `studioface/`: Django project settings, URL routing, ASGI/WSGI, Celery bootstrap
- `faces/`: models, forms, views, tasks, services, and management commands
- `templates/`: server-rendered admin, auth, landing, and guest dashboards
- `static/`: shared CSS
- `data/`: persisted FAISS indices and mapping files
- `media/`: uploaded studio photos and query images
- `frontend/`: standalone React/Vite frontend workspace
- `frontend_dist/`: built frontend assets
- `.gitignore`: comprehensive ignore patterns for Django, React, and environment files
- `.env`: local environment configuration secret and overrides

## 10. Current Notes and Constraints
- The project currently mixes a mature Django-rendered flow with a separate React frontend workspace; the Django templates are the primary user flow in the code reviewed here.
- The settings file assumes PostgreSQL by default, unlike older documentation that suggested SQLite fallback as the main path.
- Bulk upload form validation currently exposes a `max_files` widget hint, but the server-side clean method does not strictly reject uploads above that limit.
- Guest search and download behavior is event-specific and session-bound, which is central to the current product design.
