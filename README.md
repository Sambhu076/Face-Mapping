# Studio Face Finder

A Django-based face recognition web application for photography studios. The app indexes faces from uploaded event photos, stores metadata in PostgreSQL or SQLite, and performs fast similarity search with FAISS over InsightFace embeddings.

## Features

- Upload studio photos and detect/index multiple faces per image.
- Store photo metadata and per-face bounding boxes in Django models.
- Generate 512-dimensional face embeddings with InsightFace.
- Normalize vectors and search them with FAISS for fast nearest-neighbor retrieval.
- Upload a selfie or portrait query and view the best matching photos in a responsive gallery.
- Uses PostgreSQL when `POSTGRES_*` environment variables are set, otherwise falls back to SQLite for local development.

## Tech Stack

- Python, Django
- OpenCV
- InsightFace
- FAISS
- PostgreSQL or SQLite

## Project Layout

- `studioface/`: Django project configuration.
- `faces/`: Models, forms, views, and face recognition/FAISS service layer.
- `templates/`: Server-rendered UI.
- `static/`: CSS and client-side loading states.

## Setup

1. Create a virtual environment and activate it.
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Configure the database.

For PostgreSQL, set:

```bash
POSTGRES_DB=studioface
POSTGRES_USER=studioface
POSTGRES_PASSWORD=replace-me
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=600
```

If these are not set, the app uses `db.sqlite3`.

4. Run database migrations:

```bash
python manage.py migrate
```

5. Create an admin account for studio uploads:

```bash
python manage.py createsuperuser
```

6. Start the development server:

```bash
python manage.py runserver
```

7. Open `http://127.0.0.1:8000/`.

## Access Model

- Users register from the app and can search indexed photos.
- Admins are Django staff or superusers and can upload/index event photos.
- The studio admin interface is available at `/admin/`, and Django's built-in admin site is available at `/django-admin/`.

## Notes

- The first InsightFace run downloads model weights; ensure the runtime can access them.
- `faces/services.py` uses `buffalo_l` via `FaceAnalysis` and defaults to CPU mode with `INSIGHTFACE_CTX_ID=-1`.
- FAISS index files are stored under `data/`.
- Query uploads are stored under `media/queries/`. Studio images are stored under `media/studio_photos/`.
- PostgreSQL improves metadata/query performance and concurrency, but it does not remove image-download lag by itself. Large image files should remain in filesystem or object storage, then be served by Nginx or a CDN rather than Django.
- For larger event workloads, move indexing into a background worker such as Celery and rebuild or update the FAISS index asynchronously.
