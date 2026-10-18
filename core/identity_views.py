"""Private manual identity-document review. No NIMC verification is claimed."""
import hashlib
import hmac
import io
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import IdentityReview, StaffAuditEvent

MAX_IMAGE_BYTES = 2 * 1024 * 1024


@login_required
def identity_submit(request):
    review = IdentityReview.objects.filter(user=request.user).first()
    if request.method == "POST":
        if review and review.status in (IdentityReview.Status.PENDING, IdentityReview.Status.APPROVED):
            messages.error(request, "Your document is already under review or approved.")
            return redirect("identity_submit")
        nin = request.POST.get("nin", "").strip()
        picture = request.FILES.get("document")
        if not nin.isascii() or len(nin) != 11 or not nin.isdigit():
            messages.error(request, "Enter an 11-digit NIN.")
        elif not picture or picture.size > MAX_IMAGE_BYTES or picture.size < 20:
            messages.error(request, "Upload a JPG or PNG document image smaller than 2 MB.")
        else:
            from PIL import Image, UnidentifiedImageError
            try:
                picture.seek(0)
                with Image.open(picture) as im:
                    if im.format not in ("JPEG", "PNG"):
                        raise ValueError("Unsupported format")
                    im.verify()
                picture.seek(0)
                digest = hmac.new(settings.SECRET_KEY.encode(), nin.encode(), hashlib.sha256).hexdigest()
                with transaction.atomic():
                    duplicate = IdentityReview.objects.filter(nin_digest=digest).exclude(user=request.user).exists()
                    if duplicate:
                        messages.error(request, "This identity number is already linked to another account. Contact support.")
                    else:
                        if review:
                            review.document.delete(save=False)
                            review.document = picture
                            review.nin_digest = digest
                            review.nin_last_four = nin[-4:]
                            review.status = IdentityReview.Status.PENDING
                            review.review_note = ""
                            review.reviewed_by = None
                            review.reviewed_at = None
                            review.save()
                        else:
                            IdentityReview.objects.create(user=request.user, nin_digest=digest, nin_last_four=nin[-4:], document=picture)
                        messages.success(request, "Document submitted for manual review.")
                        return redirect("identity_submit")
            except (UnidentifiedImageError, ValueError, OSError):
                messages.error(request, "Invalid image. Use a valid JPG or PNG.")
            except IntegrityError:
                messages.error(request, "This identity number is already registered.")
    return render(request, "core/identity_submit.html", {"review": IdentityReview.objects.filter(user=request.user).first()})


@staff_member_required
def identity_reviews(request):
    reviews = IdentityReview.objects.select_related("user", "reviewed_by").order_by("-submitted_at")[:100]
    return render(request, "core/identity_reviews.html", {"reviews": reviews})


@staff_member_required
def identity_document(request, review_id):
    review = get_object_or_404(IdentityReview, pk=review_id)
    try:
        document = review.document.open("rb")
    except (OSError, ValueError):
        raise Http404
    response = FileResponse(document, content_type="application/octet-stream", as_attachment=True, filename="identity-document" + Path(review.document.name).suffix)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@staff_member_required
def identity_decision(request, review_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    action = request.POST.get("status")
    if action not in (IdentityReview.Status.APPROVED, IdentityReview.Status.REJECTED, IdentityReview.Status.CORRECTION):
        messages.error(request, "Invalid review decision.")
        return redirect("identity_reviews")
    with transaction.atomic():
        review = get_object_or_404(IdentityReview.objects.select_for_update(), pk=review_id)
        note = request.POST.get("note", "").strip()[:1000]
        if action != IdentityReview.Status.APPROVED and not note:
            messages.error(request, "Give a reason for rejection or correction.")
            return redirect("identity_reviews")
        review.status = action
        review.review_note = note
        review.reviewed_by = request.user
        review.reviewed_at = timezone.now()
        review.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at"])
        StaffAuditEvent.objects.create(actor=request.user, action="identity_review", target_type="identity", target_id=review.pk, details=f"Decision: {action}")
    messages.success(request, "Review decision recorded.")
    return redirect("identity_reviews")
