from django.core.management.base import BaseCommand
from faces.services import face_service, FaceServiceError
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Pre-downloads InsightFace models (buffalo_l) to the persistent volume.'

    def handle(self, *args, **options):
        self.stdout.write("Checking for InsightFace models...")
        try:
            # _build_engine triggers the model check/download
            engine = face_service._build_engine()
            if engine:
                self.stdout.write(self.style.SUCCESS("InsightFace models are ready and verified."))
            else:
                self.stdout.write(self.style.WARNING("InsightFace returned None. Check if ALLOW_OPENCV_FALLBACK is enabled."))
        except FaceServiceError as e:
            self.stdout.write(self.style.ERROR(f"InsightFace initialization failed: {e}"))
            self.stdout.write(self.style.NOTICE("This might be due to a connection issue during download. Retrying may help."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
