from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0005_identityreview")]
    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=70, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="NGN", max_length=3)),
                ("status", models.CharField(choices=[
                    ("initiated", "Initiated"), ("pending", "Pending"), ("success", "Successful"),
                    ("failed", "Failed"), ("review", "Needs review"),
                    ("refund_pending", "Refund pending"), ("refunded", "Refunded"),
                ], default="initiated", max_length=16)),
                ("gateway_status", models.CharField(blank=True, max_length=32)),
                ("authorization_url", models.URLField(blank=True, max_length=500)),
                ("refund_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="paystack_payments", to="core.booking")),
            ],
        ),
        migrations.AddConstraint(
            model_name="paymenttransaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["initiated", "pending"]),
                fields=("booking",), name="one_active_paystack_attempt",
            ),
        ),
    ]
