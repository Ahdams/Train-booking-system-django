"""Staff management of individual dated journeys."""
from django import forms
from django.db import transaction
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from .disruption_service import apply_disruption
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import JourneyDisruption, Schedule, StaffAuditEvent


class DisruptionForm(forms.ModelForm):
    class Meta:
        model = JourneyDisruption
        fields = ("schedule", "travel_date", "status", "revised_departure_time", "reason")
        widgets = {"travel_date": forms.DateInput(attrs={"type": "date"}), "reason": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        data = super().clean()
        if data.get("travel_date") and data["travel_date"] < timezone.localdate():
            self.add_error("travel_date", "Choose today or a future date.")
        status = data.get("status")
        if status == JourneyDisruption.Status.DELAYED and not data.get("revised_departure_time"):
            self.add_error("revised_departure_time", "Enter the new departure time.")
        if status == JourneyDisruption.Status.CANCELLED and data.get("revised_departure_time"):
            self.add_error("revised_departure_time", "Clear the new departure time for cancellations.")
        if not (data.get("reason") or "").strip():
            self.add_error("reason", "Explain the disruption.")
        return data


@staff_member_required
def manage_disruptions(request):
    form = DisruptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                disruption = apply_disruption(
                    schedule=data["schedule"], travel_date=data["travel_date"],
                    status=data["status"], reason=data["reason"],
                    revised_departure_time=data["revised_departure_time"],
                )
                StaffAuditEvent.objects.create(
                    actor=request.user, action="journey_disruption_updated",
                    target_type="journey_disruption", target_id=disruption.pk,
                    details=f"Journey {disruption.schedule_id} on {disruption.travel_date}: {disruption.status}",
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Journey updated. Operator cancellations refund confirmed wallet payments in full.")
            return redirect("manage_disruptions")
    disruptions = JourneyDisruption.objects.select_related(
        "schedule__train", "schedule__route__origin", "schedule__route__destination"
    ).order_by("-travel_date", "-updated_at")[:100]
    return render(request, "core/manage_disruptions.html", {"form": form, "disruptions": disruptions})
