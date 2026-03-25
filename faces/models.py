import uuid

from django.db import models
from django.utils.text import slugify


class Event(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    access_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def _generate_unique_slug(self) -> str:
        base_slug = slugify(self.name) or "event"
        slug = base_slug
        counter = 2
        while Event.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        elif self.pk:
            previous_name = Event.objects.filter(pk=self.pk).values_list("name", flat=True).first()
            if previous_name and previous_name != self.name:
                self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def ensure_slug(self) -> str:
        if self.slug:
            return self.slug
        self.slug = self._generate_unique_slug()
        Event.objects.filter(pk=self.pk).update(slug=self.slug)
        return self.slug

    @property
    def access_path(self) -> str:
        return f"/events/{self.ensure_slug()}/{self.access_key}/"


class Photo(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="photos", null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    event_name = models.CharField(max_length=255, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    original_image = models.ImageField(upload_to="studio_photos/%Y/%m/%d")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    face_count = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return self.title or self.original_image.name

    @property
    def display_event_name(self) -> str:
        if self.event_id:
            return self.event.name
        return self.event_name or "Studio Event"


class FaceEmbedding(models.Model):
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="faces")
    face_index = models.PositiveIntegerField()
    bounding_box = models.JSONField(default=dict)
    landmarks = models.JSONField(default=list, blank=True)
    detection_score = models.FloatField(default=0.0)
    embedding = models.JSONField()
    similarity_cache = models.FloatField(default=0.0, blank=True)
    person_id = models.CharField(max_length=36, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["photo_id", "face_index"]
        unique_together = ("photo", "face_index")

    def __str__(self) -> str:
        return f"Face {self.face_index} in photo {self.photo_id}"
