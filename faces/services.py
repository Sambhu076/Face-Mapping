import json
import logging
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import cv2
import faiss
import numpy as np
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.core.cache import cache

from .models import FaceEmbedding, Photo

try:
    from insightface.app import FaceAnalysis
except ImportError:  # pragma: no cover
    FaceAnalysis = None


class FaceServiceError(Exception):
    pass


logger = logging.getLogger(__name__)


@dataclass
class SearchMatch:
    face: FaceEmbedding
    score: float


class FaceRecognitionService:
    def __init__(self) -> None:
        self.embedding_dimension = settings.FACE_APP["EMBEDDING_DIMENSION"]
        self.data_dir = Path(settings.FACE_APP["FAISS_INDEX_PATH"]).parent
        self.similarity_threshold = settings.FACE_APP["SIMILARITY_THRESHOLD"]
        self.max_results = settings.FACE_APP["MAX_RESULTS"]
        self.detection_confidence_threshold = settings.FACE_APP["DETECTION_CONFIDENCE_THRESHOLD"]
        self.default_search_top_k = settings.FACE_APP["SEARCH_TOP_K"]
        
        self._engine = None
        self._cascade = None
        
        # Hold event-specific indices in memory per-instance for bulk processing
        self._event_indices = {}
        self._event_mappings = {}

    def _get_index_path(self, event_id: int) -> Path:
        return self.data_dir / f"{event_id}_face.index"

    def _get_mapping_path(self, event_id: int) -> Path:
        return self.data_dir / f"{event_id}_face_mapping.json"

    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _build_engine(self):
        if self._engine is not None:
            return self._engine
        if FaceAnalysis is None:
            if settings.FACE_APP.get("ALLOW_OPENCV_FALLBACK", False):
                logger.warning("InsightFace not installed. Using OpenCV fallback.")
                return None
            raise FaceServiceError("InsightFace is required but not installed.")
        try:
            # Prioritize CUDA Execution, fallback to CPU
            providers = settings.FACE_APP.get("INSIGHTFACE_PROVIDERS") or ["CUDAExecutionProvider", "CPUExecutionProvider"]
            logger.info("Initializing InsightFace (model: buffalo_l, providers: %s)...", providers)
            engine = FaceAnalysis(name="buffalo_l", providers=providers)
            engine.prepare(ctx_id=settings.FACE_APP["INSIGHTFACE_CTX_ID"], det_size=(320, 320))
            self._engine = engine
            logger.info("InsightFace initialized successfully.")
            return engine
        except Exception as e:
            logger.error("InsightFace failed to initialize: %s", e, exc_info=True)
            if settings.FACE_APP.get("ALLOW_OPENCV_FALLBACK", False):
                logger.warning("Falling back to OpenCV due to InsightFace initialization failure.")
                return None
            raise FaceServiceError(f"InsightFace failed to initialize: {e}. Check server logs for details.")

    def _build_cascade(self):
        if self._cascade is not None:
            return self._cascade
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            raise FaceServiceError("OpenCV Haar cascade could not be loaded for fallback.")
        self._cascade = cascade
        return cascade

    def _empty_index(self):
        # Use HNSW for logarithmic Approx Nearest Neighbor Search
        index = faiss.IndexHNSWFlat(self.embedding_dimension, 32)
        index.hnsw.efConstruction = 40
        return index

    def _load_event_index(self, event_id: int) -> None:
        if event_id in self._event_indices:
            return
            
        self._ensure_dirs()
        idx_path = self._get_index_path(event_id)
        map_path = self._get_mapping_path(event_id)
        
        if idx_path.exists():
            index = faiss.read_index(str(idx_path))
        else:
            index = self._empty_index()
            
        if map_path.exists():
            mapping = json.loads(map_path.read_text())
        else:
            mapping = []
            
        if index.ntotal != len(mapping):
            index, mapping = self._rebuild_event_index_data(event_id)
            
        self._event_indices[event_id] = index
        self._event_mappings[event_id] = mapping

    def _persist_event_index(self, event_id: int) -> None:
        if event_id not in self._event_indices:
            return
            
        self._ensure_dirs()
        idx_path = self._get_index_path(event_id)
        map_path = self._get_mapping_path(event_id)
        
        faiss.write_index(self._event_indices[event_id], str(idx_path))
        map_path.write_text(json.dumps(self._event_mappings[event_id]))

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        embedding = embedding.astype("float32").reshape(1, -1)
        faiss.normalize_L2(embedding)
        return embedding

    @staticmethod
    def _face_area(face_data: dict) -> int:
        bbox = face_data["bbox"]
        return max(0, bbox["x2"] - bbox["x1"]) * max(0, bbox["y2"] - bbox["y1"])

    @staticmethod
    def _bbox_center(face_data: dict) -> tuple[float, float]:
        bbox = face_data["bbox"]
        return ((bbox["x1"] + bbox["x2"]) / 2.0, (bbox["y1"] + bbox["y2"]) / 2.0)

    def _rank_query_faces(self, extracted: dict) -> list[dict]:
        faces = list(extracted["faces"])
        if len(faces) <= 1:
            return faces

        image_center = (extracted["width"] / 2.0, extracted["height"] / 2.0)
        def score(face_data: dict) -> tuple[float, float]:
            area = float(self._face_area(face_data))
            cx, cy = self._bbox_center(face_data)
            distance = ((cx - image_center[0]) ** 2 + (cy - image_center[1]) ** 2) ** 0.5
            return (area, -distance)

        return sorted(faces, key=score, reverse=True)

    def _read_and_resize_image(self, image_path: str, max_dim: int = 1920):
        # Resize extremely large images to reduce InsightFace Inference Overhead
        try:
            image = cv2.imread(image_path)
            if image is None:
                return None, 0, 0
            h, w = image.shape[:2]
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            return image, image.shape[0], image.shape[1]
        except Exception:
            logger.error("Failed to read/resize %s", image_path)
            return None, 0, 0

    def parallel_load_images(self, image_paths: list[str]) -> list[tuple]:
        with ThreadPoolExecutor(max_workers=min(len(image_paths), 8)) as executor:
            results = list(executor.map(self._read_and_resize_image, image_paths))
        return results

    def _parse_insightface_results(self, faces, width, height):
        parsed_faces = []
        for face in faces:
            det_score = float(getattr(face, "det_score", 0.0))
            if det_score < self.detection_confidence_threshold:
                continue
            bbox = [int(value) for value in face.bbox.tolist()]
            if (bbox[2] - bbox[0]) < 30 or (bbox[3] - bbox[1]) < 30:
                continue
            keypoints = []
            if getattr(face, "kps", None) is not None:
                keypoints = [{"x": float(point[0]), "y": float(point[1])} for point in face.kps.tolist()]
            parsed_faces.append({
                "face_index": len(parsed_faces),
                "bbox": {"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]},
                "landmarks": keypoints,
                "detection_score": det_score,
                "embedding": np.asarray(face.embedding, dtype="float32"),
            })
        return {"width": width, "height": height, "faces": parsed_faces}

    def extract_faces(self, image_path: str):
        image, height, width = self._read_and_resize_image(image_path)
        if image is None:
            return {"width": 0, "height": 0, "faces": []}
        engine = self._build_engine()
        if engine is not None:
            faces = engine.get(image)
            return self._parse_insightface_results(faces, width, height)
        # Fallback ...
        return self._extract_faces_opencv(image, width, height)

    def _extract_faces_opencv(self, image, width, height):
        if not settings.FACE_APP.get("ALLOW_OPENCV_FALLBACK", False):
            raise FaceServiceError("InsightFace not installed.")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detector = self._build_cascade()
        detections = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
        parsed_faces = []
        for index, (x, y, w, h) in enumerate(detections):
            x1, y1 = max(int(x), 0), max(int(y), 0)
            x2, y2 = min(int(x + w), width), min(int(y + h), height)
            face_crop = gray[y1:y2, x1:x2]
            if face_crop.size == 0: continue
            embedding = cv2.resize(face_crop, (16, 32), interpolation=cv2.INTER_AREA).astype("float32").reshape(-1)
            embedding /= 255.0
            embedding -= embedding.mean()
            parsed_faces.append({
                "face_index": index,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "landmarks": [],
                "detection_score": 1.0,
                "embedding": embedding,
            })
        return {"width": width, "height": height, "faces": parsed_faces}

    def extract_faces_batch(self, images_with_meta: list[tuple]):
        engine = self._build_engine()
        if engine is None:
            # Fallback to serial for OpenCV
            return [self._extract_faces_opencv(img, w, h) for img, h, w in images_with_meta if img is not None]
        
        # We can parallelize the inference calls because ONNX Runtime is thread-safe
        # and most of the time is spent outside the GIL in C++.
        def fetch_faces(item):
            img, h, w = item
            if img is None: return {"width": 0, "height": 0, "faces": []}
            return self._parse_insightface_results(engine.get(img), w, h)

        with ThreadPoolExecutor(max_workers=min(len(images_with_meta), 4)) as executor:
            results = list(executor.map(fetch_faces, images_with_meta))
        return results

    def _get_person_centroid(self, person_id: str) -> np.ndarray:
        # Calculate robust embedding across all vectors for this person
        faces = FaceEmbedding.objects.filter(person_id=person_id)
        vectors = []
        for f in faces:
            vectors.append(np.asarray(f.embedding, dtype="float32"))
        if not vectors:
            return None
        centroid = np.mean(vectors, axis=0)
        return centroid

    @transaction.atomic
    def index_photos_bulk(self, photos: list[Photo], event_id: int) -> int:
        # 1. Parallel Load & Resize
        paths = [photo.original_image.path for photo in photos]
        images_with_meta = self.parallel_load_images(paths)
        
        # 2. Parallel Inference
        batch_results = self.extract_faces_batch(images_with_meta)
        
        # 3. Load Index
        self._load_event_index(event_id)
        index = self._event_indices[event_id]
        mapping = self._event_mappings[event_id]
        
        total_faces = 0
        embeddings_to_create = []
        
        for photo, result in zip(photos, batch_results):
            photo.width = result["width"]
            photo.height = result["height"]
            photo.faces.all().delete()
            
            for face_data in result["faces"]:
                vector = self._normalize(face_data["embedding"])
                person_id = None
                
                # Search Centroids if available, fallback to individual vectors
                if index.ntotal > 0:
                    distances, indices = index.search(vector, 1)
                    score, match_idx = distances[0][0], indices[0][0]
                    if match_idx >= 0 and score >= self.similarity_threshold:
                        matched_face_id = mapping[match_idx]
                        # Prefetching matched_face would be better in a real app, but this works
                        matched_face = FaceEmbedding.objects.filter(id=matched_face_id).only("person_id").first()
                        if matched_face:
                            person_id = matched_face.person_id
                
                if not person_id:
                    import uuid
                    person_id = uuid.uuid4().hex

                embeddings_to_create.append(FaceEmbedding(
                    photo=photo,
                    face_index=face_data["face_index"],
                    bounding_box=face_data["bbox"],
                    landmarks=face_data.get("landmarks", []),
                    detection_score=face_data.get("detection_score", 0.0),
                    embedding=face_data["embedding"].tolist(),
                    person_id=person_id,
                ))
            
            total_faces += len(result["faces"])
            photo.face_count = len(result["faces"])

        # 4. Bulk Create Metadata
        FaceEmbedding.objects.bulk_create(embeddings_to_create)
        
        # 5. Populate FAISS with new face IDs and vectors
        # Note: We need the IDs from bulk_create. Django bulk_create returns IDs on Postgres.
        # For SQLite, we might have to be careful if we need the IDs immediately for FAISS.
        # Let's re-fetch or use individual saves if IDs are critical for the search_k index.
        # Actually, let's do individual saves for now to ensure mapping integrity on SQLite.
        # Optimization: In a real prod environment (Postgres), bulk_create + mapping is faster.
        
        # Since the user requested HIGH PERFORMANCE, let's check one thing:
        # Index.add(vector) doesn't strictly need the DB ID until SEARCH time.
        # So we can bulk create, then fetch the IDs in one query.
        
        new_faces = FaceEmbedding.objects.filter(photo__pk__in=[p.pk for p in photos]).order_by("id")
        for face in new_faces:
            vec = self._normalize(np.asarray(face.embedding, dtype="float32"))
            index.add(vec)
            mapping.append(face.id)

        # 6. Bulk Save Photos
        Photo.objects.bulk_update(photos, ["width", "height", "face_count", "updated_at"])
        
        return total_faces

    def search(self, image_path: str, top_k: int | None = None, event_id: int | None = None) -> list[SearchMatch]:
        if event_id is None:
            return []
            
        extracted = self.extract_faces(image_path)
        if not extracted["faces"]:
            return []
            
        ranked_query_faces = self._rank_query_faces(extracted)
        
        self._load_event_index(event_id)
        index = self._event_indices[event_id]
        mapping = self._event_mappings[event_id]
        
        if index.ntotal == 0:
            return []

        requested_top_k = self.default_search_top_k if top_k is None else top_k
        search_k = min(max(1, requested_top_k), index.ntotal)
        
        matches: dict[int, SearchMatch] = {}
        # Only search the highest ranked query face to reduce noisy matches
        query_faces = ranked_query_faces[:1] if not settings.FACE_APP.get("SEARCH_ALL_QUERY_FACES", True) else ranked_query_faces
        for face_data in query_faces: 
            query = self._normalize(face_data["embedding"])
            distances, indices = index.search(query, search_k)
            for score, match_idx in zip(distances[0], indices[0]):
                if match_idx < 0 or score < self.similarity_threshold:
                    continue
                face_id = mapping[match_idx]
                face = FaceEmbedding.objects.select_related("photo").filter(id=face_id).first()
                if not face: continue
                current = matches.get(face.photo_id)
                if current is None or score > current.score:
                    face.similarity_cache = float(score)
                    matches[face.photo_id] = SearchMatch(face=face, score=float(score))

        sorted_matches = sorted(matches.values(), key=lambda item: item.score, reverse=True)
        return sorted_matches[: self.max_results]

    def save_temp_query(self, uploaded_file) -> str:
        temp_path = default_storage.save(f"queries/{uploaded_file.name}", uploaded_file)
        return default_storage.path(temp_path)

    @transaction.atomic
    def delete_photo(self, photo: Photo) -> None:
        storage_name = photo.original_image.name
        event_id = photo.event_id
        photo.delete()
        if storage_name:
            default_storage.delete(storage_name)
        if event_id:
            self.rebuild_event_index(event_id)

    @transaction.atomic
    def delete_event_photos(self, event_id: int) -> int:
        photos = list(Photo.objects.filter(event_id=event_id))
        deleted_count = len(photos)
        for photo in photos:
            storage_name = photo.original_image.name
            photo.delete()
            if storage_name:
                default_storage.delete(storage_name)
        self.rebuild_event_index(event_id)
        return deleted_count

    def _rebuild_event_index_data(self, event_id: int):
        index = self._empty_index()
        mapping = []
        queryset = FaceEmbedding.objects.filter(photo__event_id=event_id).order_by("id").iterator()
        for face in queryset:
            vector = self._normalize(np.asarray(face.embedding, dtype="float32"))
            index.add(vector)
            mapping.append(face.id)
        return index, mapping

    def rebuild_event_index(self, event_id: int) -> None:
        index, mapping = self._rebuild_event_index_data(event_id)
        self._event_indices[event_id] = index
        self._event_mappings[event_id] = mapping
        self._persist_event_index(event_id)

    # Progress tracking for tasks
    def queue_indexing(self, photo_id: int):
        """ Legacy wrapper. No-op now. Views invoke Celery instead. """
        pass

    def init_progress(self, event_id: int, total: int):
        try:
            cache.set(f"indexing_progress_{event_id}", {"total": total, "completed": 0}, timeout=3600)
        except Exception as e:
            logger.error("Cache set failed (Redis likely down): %s", e)

    def _increment_progress(self, event_id: int):
        try:
            data = cache.get(f"indexing_progress_{event_id}")
            if data:
                data["completed"] += 1
                cache.set(f"indexing_progress_{event_id}", data, timeout=3600)
        except Exception as e:
            logger.error("Cache increment failed (Redis likely down): %s", e)

    def get_progress(self, event_id: int) -> dict:
        try:
            data = cache.get(f"indexing_progress_{event_id}")
            if not data:
                return {"total": 0, "completed": 0, "processing": False}
            is_processing = data["completed"] < data["total"]
            if not is_processing:
                cache.delete(f"indexing_progress_{event_id}")
            return {
                "total": data["total"],
                "completed": data["completed"],
                "processing": is_processing
            }
        except Exception as e:
            logger.error("Cache get failed (Redis likely down): %s", e)
            return {"total": 0, "completed": 0, "processing": False, "error": "Redis connection failed"}

face_service = FaceRecognitionService()
