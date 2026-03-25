import uuid

from django.db import migrations, models
import django.db.models.deletion


def create_events_from_photo_names(apps, schema_editor):
    Event = apps.get_model("faces", "Event")
    Photo = apps.get_model("faces", "Photo")

    for photo in Photo.objects.exclude(event_name="").iterator():
        event, _ = Event.objects.get_or_create(name=photo.event_name)
        photo.event_id = event.id
        photo.save(update_fields=["event"])


class Migration(migrations.Migration):
    dependencies = [
        ("faces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=255, unique=True)),
                ("event_date", models.DateField(blank=True, null=True)),
                ("access_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="photo",
            name="event",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="faces.event"),
        ),
        migrations.RunPython(create_events_from_photo_names, migrations.RunPython.noop),
    ]
