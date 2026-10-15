# Generated schema migration for RailFlow Phase 2.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q, F

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Station', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('code', models.CharField(max_length=12, unique=True)),
            ('name', models.CharField(max_length=120)),
            ('city', models.CharField(max_length=100)),
            ('state', models.CharField(max_length=100)),
            ('is_active', models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name='Train', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('code', models.CharField(max_length=24, unique=True)),
            ('name', models.CharField(max_length=120)),
            ('is_active', models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name='Route', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(blank=True, max_length=160)),
            ('is_active', models.BooleanField(default=True)),
            ('origin', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='departing_routes', to='core.station')),
            ('destination', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='arriving_routes', to='core.station')),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('origin', 'destination'), name='unique_route_direction'),
            models.CheckConstraint(condition=~Q(origin=F('destination')), name='different_route_stations'),
        ]}),
        migrations.CreateModel(name='Coach', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('code', models.CharField(max_length=12)),
            ('travel_class', models.CharField(choices=[('standard','Standard'),('first','First Class'),('executive','Executive')], max_length=16)),
            ('train', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='coaches', to='core.train')),
        ], options={'constraints': [models.UniqueConstraint(fields=('train', 'code'), name='unique_coach_per_train')]}),
        migrations.CreateModel(name='Seat', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('label', models.CharField(max_length=12)),
            ('is_active', models.BooleanField(default=True)),
            ('coach', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='seats', to='core.coach')),
        ], options={'constraints': [models.UniqueConstraint(fields=('coach', 'label'), name='unique_seat_per_coach')]}),
        migrations.CreateModel(name='Schedule', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('departure_time', models.TimeField()),
            ('arrival_time', models.TimeField()),
            ('operates_monday', models.BooleanField(default=True)),
            ('operates_tuesday', models.BooleanField(default=True)),
            ('operates_wednesday', models.BooleanField(default=True)),
            ('operates_thursday', models.BooleanField(default=True)),
            ('operates_friday', models.BooleanField(default=True)),
            ('operates_saturday', models.BooleanField(default=True)),
            ('operates_sunday', models.BooleanField(default=True)),
            ('is_active', models.BooleanField(default=True)),
            ('route', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='schedules', to='core.route')),
            ('train', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='schedules', to='core.train')),
        ]),
        migrations.CreateModel(name='Fare', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('travel_class', models.CharField(choices=[('standard','Standard'),('first','First Class'),('executive','Executive')], max_length=16)),
            ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
            ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fares', to='core.schedule')),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('schedule', 'travel_class'), name='unique_fare_class_schedule'),
            models.CheckConstraint(condition=Q(amount__gte=0), name='fare_nonnegative'),
        ]}),
        migrations.CreateModel(name='Booking', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('reference', models.CharField(max_length=32, unique=True)),
            ('travel_date', models.DateField()),
            ('passenger_name', models.CharField(max_length=150)),
            ('fare_paid', models.DecimalField(decimal_places=2, max_digits=12)),
            ('status', models.CharField(choices=[('held','Held'),('confirmed','Confirmed'),('cancelled','Cancelled'),('expired','Expired')], default='held', max_length=12)),
            ('hold_expires_at', models.DateTimeField(blank=True, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='core.schedule')),
            ('seat', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='core.seat')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rail_bookings', to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('schedule', 'travel_date', 'seat'), condition=Q(status__in=['held','confirmed']), name='one_active_booking_per_departure_seat'),
            models.CheckConstraint(condition=Q(fare_paid__gte=0), name='booking_fare_nonnegative'),
        ]}),
        migrations.CreateModel(name='Wallet', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='rail_wallet', to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [models.CheckConstraint(condition=Q(balance__gte=0), name='wallet_balance_nonnegative')]}),
        migrations.CreateModel(name='WalletTransaction', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('kind', models.CharField(choices=[('credit','Credit'),('debit','Debit'),('refund','Refund')], max_length=8)),
            ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
            ('balance_after', models.DecimalField(decimal_places=2, max_digits=12)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='wallet_transactions', to='core.booking')),
            ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='core.wallet')),
        ], options={'constraints': [models.CheckConstraint(condition=Q(amount__gt=0), name='wallet_transaction_positive')]}),
        migrations.CreateModel(name='PassengerReport', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('subject', models.CharField(max_length=160)),
            ('description', models.TextField()),
            ('status', models.CharField(choices=[('open','Open'),('in_progress','In progress'),('resolved','Resolved')], default='open', max_length=16)),
            ('admin_response', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.booking')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rail_reports', to=settings.AUTH_USER_MODEL)),
        ]),
    ]
