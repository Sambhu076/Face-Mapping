from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("faces", "0002_event_photo_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="faceembedding",
            name="detection_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="faceembedding",
            name="landmarks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
