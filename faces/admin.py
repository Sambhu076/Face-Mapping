from django.contrib import admin

from .models import Event, FaceEmbedding, Photo


class FaceEmbeddingInline(admin.TabularInline):
    model = FaceEmbedding
    extra = 0
    readonly_fields = ("face_index", "similarity_cache")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "event_date", "created_at")
    search_fields = ("name", "slug")


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "uploaded_at", "face_count")
    search_fields = ("title", "event__name", "event_name")
    inlines = [FaceEmbeddingInline]


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "photo", "face_index", "created_at")
    list_select_related = ("photo",)
