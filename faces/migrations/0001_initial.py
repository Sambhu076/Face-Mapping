from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Photo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=255)),
                ("event_name", models.CharField(blank=True, max_length=255)),
                ("captured_at", models.DateTimeField(blank=True, null=True)),
                ("original_image", models.ImageField(upload_to="studio_photos/%Y/%m/%d")),
                ("width", models.PositiveIntegerField(default=0)),
                ("height", models.PositiveIntegerField(default=0)),
                ("face_count", models.PositiveIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
        migrations.CreateModel(
            name="FaceEmbedding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("face_index", models.PositiveIntegerField()),
                ("bounding_box", models.JSONField(default=dict)),
                ("embedding", models.JSONField()),
                ("similarity_cache", models.FloatField(blank=True, default=0.0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("photo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="faces", to="faces.photo")),
            ],
            options={"ordering": ["photo_id", "face_index"], "unique_together": {("photo", "face_index")}},
        ),
    ]
