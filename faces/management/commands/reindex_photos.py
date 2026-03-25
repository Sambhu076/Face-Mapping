from django.core.management.base import BaseCommand

from faces.models import Photo
from faces.services import FaceServiceError, face_service


class Command(BaseCommand):
    help = "Re-extract and reindex all stored photo face embeddings using the current engine."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-id",
            type=int,
            help="Only reindex photos for the given event ID.",
        )

    def handle(self, *args, **options):
        queryset = Photo.objects.order_by("id")
        event_id = options.get("event_id")
        if event_id is not None:
            queryset = queryset.filter(event_id=event_id)

        photos = list(queryset)
        total = len(photos)
        if total == 0:
            self.stdout.write(self.style.WARNING("No photos found to reindex."))
            return

        success_count = 0
        failure_count = 0

        for index, photo in enumerate(photos, start=1):
            label = photo.title or photo.original_image.name
            self.stdout.write(f"[{index}/{total}] Reindexing photo {photo.id}: {label}")
            try:
                face_service.index_photo(photo)
                success_count += 1
            except FaceServiceError as exc:
                failure_count += 1
                self.stderr.write(
                    self.style.ERROR(f"Failed photo {photo.id} ({label}): {exc}")
                )

        summary = f"Reindex complete. Success: {success_count}. Failed: {failure_count}."
        if failure_count:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
