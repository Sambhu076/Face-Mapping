import logging
from celery import shared_task
from django.db import transaction
from .models import Photo, Event
from .services import face_service

logger = logging.getLogger(__name__)

@shared_task
def process_photo_bulk_task(photo_ids: list[int], event_id: int):
    """
    Celery task that receives a batch of uploaded photo IDs for a specific event
    and passes them to the face_service for high-performance parallel indexing.
    """
    from .services import face_service
    
    logger.info("Starting optimized parallel processing for %s photos in event_id=%s", len(photo_ids), event_id)
    
    photos = list(Photo.objects.filter(id__in=photo_ids))
    if not photos:
        return {"success": 0, "failed": 0}
        
    success_count = 0
    failure_count = 0
    
    try:
        # Use the NEW high-performance bulk method
        # This handles parallel loading, parallel inference, and bulk DB saves
        success_count = face_service.index_photos_bulk(photos, event_id)
        
        # Manually update the progress counter by the number of processed photos
        # to keep the frontend progress bar accurate.
        for _ in range(success_count):
            face_service._increment_progress(event_id)
            
        # Save the updated FAISS index back to disk after the bulk processing is complete
        face_service._persist_event_index(event_id)
        
    except Exception as e:
        logger.exception("Bulk indexing failed for event_id=%s: %s", event_id, e)
        failure_count = len(photo_ids) - success_count
        # Ensure progress is still marked as 'done' for the total batch to avoid stuck bars
        for _ in range(len(photo_ids)):
            face_service._increment_progress(event_id)
    
    logger.info("Finished optimized bulk processing for event_id=%s: %s success", event_id, success_count)
    return {"success": success_count, "failed": failure_count}
