from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='JourneyDisruption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('travel_date', models.DateField()),
                ('status', models.CharField(max_length=12, choices=[('delayed', 'Delayed'), ('cancelled', 'Cancelled')])),
                ('reason', models.TextField()),
                ('revised_departure_time', models.TimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='disruptions', to='core.schedule')),
            ],
        ),
        migrations.AddConstraint(
            model_name='journeydisruption',
            constraint=models.UniqueConstraint(fields=('schedule', 'travel_date'), name='unique_dated_disruption'),
        ),
    ]
