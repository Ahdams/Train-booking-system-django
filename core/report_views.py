"""Passenger support requests and staff responses."""
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .models import Booking, PassengerReport


class PassengerReportForm(forms.ModelForm):
    class Meta:
        model = PassengerReport
        fields = ("booking", "subject", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["booking"].queryset = Booking.objects.filter(user=user).order_by("-created_at")
        self.fields["booking"].required = False


class StaffResponseForm(forms.ModelForm):
    class Meta:
        model = PassengerReport
        fields = ("status", "admin_response")
        widgets = {"admin_response": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        data = super().clean()
        if data.get("status") == PassengerReport.Status.RESOLVED and not data.get("admin_response", "").strip():
            self.add_error("admin_response", "Explain the resolution before marking a report resolved.")
        return data


@login_required
def reports(request):
    form = PassengerReportForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.user = request.user
        report.save()
        messages.success(request, "Your report was submitted.")
        return redirect("reports")
    items = PassengerReport.objects.filter(user=request.user).select_related("booking").order_by("-created_at")
    return render(request, "core/reports.html", {"form": form, "reports": items})


@staff_member_required
def staff_reports(request):
    items = PassengerReport.objects.select_related("user", "booking").order_by("-created_at")
    return render(request, "core/staff_reports.html", {"reports": items})


@staff_member_required
def staff_report_detail(request, report_id):
    report = get_object_or_404(PassengerReport, pk=report_id)
    form = StaffResponseForm(request.POST or None, instance=report)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Report updated.")
        return redirect("staff_reports")
    return render(request, "core/staff_report_detail.html", {"report": report, "form": form})
