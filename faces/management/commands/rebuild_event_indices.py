from django.core.management.base import BaseCommand
from faces.models import Event
from faces.services import face_service

class Command(BaseCommand):
    help = 'Rebuilds event-specific FAISS HNSW indices from existing database embeddings (Migration to new architecture).'

    def handle(self, *args, **options):
        events = Event.objects.all()
        
        if not events.exists():
            self.stdout.write(self.style.WARNING("No events found in the database."))
            return
            
        for event in events:
            self.stdout.write(f"Rebuilding HNSW index for Event: {event.name} (ID: {event.id})...")
            try:
                face_service.rebuild_event_index(event.id)
                self.stdout.write(self.style.SUCCESS(f"Successfully rebuilt FAISS index for {event.name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to rebuild index for {event.name}: {e}"))
