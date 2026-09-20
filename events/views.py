import base64
import json
import shutil
import tempfile
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import qrcode
from cloudinary.exceptions import Error as CloudinaryError
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import PhotoForm
from .models import Event, Photo, Reaction
from .services import (
    REACTION_ANNOTATIONS,
    encode_cursor,
    encode_cursor_values,
    ensure_session,
    gallery_queryset,
    newer_than,
    page_before,
    record_upload_attempt,
    upload_rate_status,
)


def home(request):
    event = Event.objects.order_by("date").first()
    return event_detail(request, event.slug) if event else render(request, "events/no_event.html")


def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug)
    queryset = gallery_queryset(event, request)
    photos, next_cursor = page_before(queryset, "")
    latest_cursor = encode_cursor(photos[0]) if photos else encode_cursor_values(timezone.now(), 0)
    return render(request, "events/detail.html", {
        "event": event,
        "photos": photos,
        "next_cursor": next_cursor,
        "latest_cursor": latest_cursor,
        "form": PhotoForm(),
        "categories": Photo.Category.choices,
        "poll_seconds": settings.GALLERY_POLL_SECONDS,
    })


@require_POST
def upload_photo(request, slug):
    event = get_object_or_404(Event, slug=slug)
    limited, session_hash, ip_hash = upload_rate_status(request, event)
    if limited:
        form = PhotoForm(request.POST)
        message = "Muitas fotos foram enviadas em pouco tempo. Seus textos foram preservados; aguarde um instante, escolha a foto novamente e tente outra vez."
        response = render(request, "components/upload_form.html", {"form": form, "event": event, "upload_error": message}, status=429)
        response["Retry-After"] = str(settings.UPLOAD_RATE_BURST_SECONDS)
        return response

    record_upload_attempt(event, session_hash, ip_hash)
    form = PhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "components/upload_form.html", {
            "form": form,
            "event": event,
            "upload_error": "Revise os dados abaixo. Talvez seja necessário escolher a foto novamente.",
        }, status=422)

    try:
        photo = form.save(commit=False)
        photo.event = event
        photo.is_approved = settings.AUTO_APPROVE_UPLOADS
        with transaction.atomic():
            photo.save()
    except (OSError, DatabaseError, CloudinaryError):
        if "photo" in locals() and photo.image and photo.image._committed:
            try:
                photo.image.delete(save=False)
            except (OSError, CloudinaryError):
                pass
        return render(request, "components/upload_form.html", {
            "form": PhotoForm(request.POST),
            "event": event,
            "upload_error": "Não conseguimos guardar a foto agora. Seus textos foram preservados; escolha a imagem novamente e tente outra vez.",
        }, status=503)

    if request.headers.get("HX-Request"):
        html = ""
        if photo.is_approved:
            photo = gallery_queryset(event, request).get(pk=photo.pk)
            html = render_to_string("components/photo_card.html", {"photo": photo}, request=request)
        response = HttpResponse(html)
        response["HX-Trigger"] = json.dumps({"uploadSuccess": {"cursor": encode_cursor(photo)}})
        response["HX-Retarget"] = "#gallery"
        response["HX-Reswap"] = "afterbegin"
        response["X-Latest-Cursor"] = encode_cursor(photo)
        return response
    return JsonResponse({"ok": True, "approved": photo.is_approved})


@require_GET
def photo_page(request, slug):
    event = get_object_or_404(Event, slug=slug)
    category = request.GET.get("category", "")
    queryset = gallery_queryset(event, request, category)
    photos, next_cursor = page_before(queryset, request.GET.get("before", ""))
    return render(request, "components/photo_page.html", {
        "photos": photos,
        "next_cursor": next_cursor,
        "event": event,
        "category": category,
        "is_initial_filter": not request.GET.get("before"),
    })


@require_GET
def photo_updates(request, slug):
    event = get_object_or_404(Event, slug=slug)
    category = request.GET.get("category", "")
    queryset = gallery_queryset(event, request, category)
    photos = list(newer_than(queryset, request.GET.get("after", "")))
    latest_cursor = encode_cursor(photos[0]) if photos else request.GET.get("after", "")
    return JsonResponse({"count": len(photos), "cursor": latest_cursor})


@require_GET
def photo_newer(request, slug):
    event = get_object_or_404(Event, slug=slug)
    category = request.GET.get("category", "")
    photos = list(newer_than(gallery_queryset(event, request, category), request.GET.get("after", "")))
    response = render(request, "components/new_photos.html", {"photos": photos})
    if photos:
        response["X-Latest-Cursor"] = encode_cursor(photos[0])
    return response


@require_GET
def photo_detail(request, pk):
    photo = get_object_or_404(Photo.objects.filter(is_approved=True).annotate(**REACTION_ANNOTATIONS), pk=pk)
    category = request.GET.get("category", "")
    neighbors = photo.event.photos.filter(is_approved=True)
    if category in Photo.Category.values:
        neighbors = neighbors.filter(category=category)
    newer = neighbors.filter(Q(created_at__gt=photo.created_at) | Q(created_at=photo.created_at, id__gt=photo.id)).order_by("created_at", "id").first()
    older = neighbors.filter(Q(created_at__lt=photo.created_at) | Q(created_at=photo.created_at, id__lt=photo.id)).order_by("-created_at", "-id").first()
    ensure_session(request)
    photo.current_session_reactions = list(photo.reactions.filter(session_key=request.session.session_key))
    return render(request, "events/photo_detail.html", {"photo": photo, "previous": newer, "next": older, "category": category})


@require_POST
def react(request, pk):
    photo = get_object_or_404(Photo, pk=pk, is_approved=True)
    session_key = ensure_session(request)
    emoji = request.POST.get("emoji")
    if emoji not in Reaction.Emoji.values:
        raise Http404
    reaction, created = Reaction.objects.get_or_create(photo=photo, session_key=session_key, emoji=emoji)
    if not created:
        reaction.delete()
    photo = Photo.objects.filter(pk=pk).annotate(**REACTION_ANNOTATIONS).get()
    photo.current_session_reactions = list(photo.reactions.filter(session_key=session_key))
    return render(request, "components/reactions.html", {"photo": photo})


@require_GET
def share_text(request, slug):
    event = get_object_or_404(Event, slug=slug)
    public_url = request.build_absolute_uri(reverse("event-detail", kwargs={"slug": event.slug}))
    return JsonResponse({"text": f"Veja e compartilhe as lembranças do casamento de {event.name} 🤍", "url": public_url})


@login_required
def couple_dashboard(request):
    event = get_object_or_404(Event, pk=request.GET.get("event")) if request.GET.get("event") else Event.objects.order_by("date").first()
    photos = event.photos.all() if event else Photo.objects.none()
    return render(request, "couple/dashboard.html", {
        "event": event,
        "total": photos.count(),
        "guests": photos.exclude(guest_name="").values("guest_name").distinct().count(),
        "today": photos.filter(created_at__date=date.today()).count(),
        "reactions": Reaction.objects.filter(photo__event=event).count() if event else 0,
        "latest": photos.select_related("event")[:12],
    })


@login_required
def download_photo(request, pk):
    photo = get_object_or_404(Photo, pk=pk)
    photo.image.open("rb")
    suffix = Path(photo.image.name).suffix or ".jpg"
    return FileResponse(photo.image, as_attachment=True, filename=f"foto-{photo.id}{suffix}")


@login_required
def download_album(request, pk):
    event = get_object_or_404(Event, pk=pk)
    archive_file = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    used_names = set()
    with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for photo in event.photos.iterator(chunk_size=50):
            suffix = Path(photo.image.name).suffix.lower() or ".jpg"
            name = f"{photo.created_at:%Y%m%d-%H%M%S}-{photo.id}{suffix}"
            if name in used_names:
                name = f"{photo.id}-{name}"
            used_names.add(name)
            try:
                photo.image.open("rb")
                with archive.open(name, "w") as target:
                    shutil.copyfileobj(photo.image, target, length=1024 * 1024)
                photo.image.close()
            except (OSError, CloudinaryError):
                continue
    archive_file.seek(0)
    return FileResponse(archive_file, as_attachment=True, filename=f"album-{event.slug}.zip", content_type="application/zip")


@login_required
def qrcode_page(request, pk):
    event = get_object_or_404(Event, pk=pk)
    url = f"{settings.EVENT_BASE_URL.rstrip('/')}/e/{event.slug}/"
    qr = qrcode.make(url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return render(request, "events/qrcode.html", {"event": event, "qr": base64.b64encode(buffer.getvalue()).decode(), "url": url})


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
