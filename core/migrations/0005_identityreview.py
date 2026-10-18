from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("core", "0004_staffauditevent"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="IdentityReview", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("nin_digest", models.CharField(max_length=64, unique=True)),
            ("nin_last_four", models.CharField(max_length=4)),
            ("document", models.FileField(upload_to="identity_documents/")),
            ("status", models.CharField(choices=[("pending","Pending review"),("approved","Document reviewed"),("rejected","Rejected"),("correction","Correction requested")], default="pending", max_length=12)),
            ("review_note", models.TextField(blank=True)),
            ("reviewed_at", models.DateTimeField(blank=True, null=True)),
            ("submitted_at", models.DateTimeField(auto_now_add=True)),
            ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="identity_decisions", to=settings.AUTH_USER_MODEL)),
            ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="identity_review", to=settings.AUTH_USER_MODEL)),
        ])
    ]
