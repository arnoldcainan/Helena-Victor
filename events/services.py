import base64
import json
from io import BytesIO
from datetime import timedelta
from uuid import uuid4

from PIL import Image, ImageOps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.signing import salted_hmac
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Photo, Reaction, UploadAttempt


SANITIZED_FORMATS = {
    "JPEG": {"extension": ".jpg", "mime": "image/jpeg"},
    "PNG": {"extension": ".png", "mime": "image/png"},
    "WEBP": {"extension": ".webp", "mime": "image/webp"},
}


def sanitize_uploaded_image(uploaded, detected_format):
    """Apply EXIF orientation and rewrite once without EXIF or ancillary metadata."""
    uploaded.seek(0)
    output = BytesIO()
    with Image.open(uploaded) as source:
        icc_profile = source.info.get("icc_profile")
        source.load()
        ImageOps.exif_transpose(source, in_place=True)
        source.info.clear()
        clean = source
        save_options = {}
        if icc_profile:
            save_options["icc_profile"] = icc_profile
        if detected_format == "JPEG":
            if clean.mode not in {"RGB", "L"}:
                clean = source.convert("RGB")
            save_options.update(quality=95, optimize=True, progressive=True)
        elif detected_format == "PNG":
            save_options.update(optimize=True)
        elif detected_format == "WEBP":
            save_options.update(quality=95, method=4)

        try:
            clean.save(output, format=detected_format, **save_options)
        finally:
            if clean is not source:
                clean.close()

    info = SANITIZED_FORMATS[detected_format]
    safe_name = f"{uuid4().hex}{info['extension']}"
    return SimpleUploadedFile(safe_name, output.getvalue(), content_type=info["mime"])


REACTION_ANNOTATIONS = {
    f"{code}_count": Count("reactions", filter=Q(reactions__emoji=code), distinct=True)
    for code, _label in Reaction.Emoji.choices
}


def ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def gallery_queryset(event, request, category=""):
    session_key = ensure_session(request)
    queryset = event.photos.filter(is_approved=True)
    if category in Photo.Category.values:
        queryset = queryset.filter(category=category)
    return queryset.annotate(**REACTION_ANNOTATIONS).order_by("-created_at", "-id").prefetch_related(
        Prefetch("reactions", queryset=Reaction.objects.filter(session_key=session_key), to_attr="current_session_reactions")
    )


def encode_cursor(photo):
    return encode_cursor_values(photo.created_at, photo.id)


def encode_cursor_values(created_at, photo_id):
    payload = json.dumps([created_at.isoformat(), photo_id]).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value):
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        created_at, photo_id = json.loads(base64.urlsafe_b64decode(padded).decode())
        return parse_datetime(created_at), int(photo_id)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def page_before(queryset, cursor, page_size=20):
    decoded = decode_cursor(cursor)
    if decoded:
        created_at, photo_id = decoded
        queryset = queryset.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=photo_id))
    items = list(queryset[: page_size + 1])
    has_more = len(items) > page_size
    items = items[:page_size]
    return items, encode_cursor(items[-1]) if has_more and items else ""


def newer_than(queryset, cursor, limit=50):
    decoded = decode_cursor(cursor)
    if not decoded:
        return queryset.none()
    created_at, photo_id = decoded
    return queryset.filter(Q(created_at__gt=created_at) | Q(created_at=created_at, id__gt=photo_id)).order_by("-created_at", "-id")[:limit]


def _hash_identifier(value, namespace):
    return salted_hmac(namespace, value or "unknown").hexdigest()


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")


def upload_rate_status(request, event):
    session_hash = _hash_identifier(ensure_session(request), "upload-session")
    ip_hash = _hash_identifier(client_ip(request), "upload-ip")
    now = timezone.now()
    burst_since = now - timedelta(seconds=settings.UPLOAD_RATE_BURST_SECONDS)
    window_since = now - timedelta(seconds=settings.UPLOAD_RATE_WINDOW_SECONDS)
    attempts = UploadAttempt.objects.filter(event=event)
    limited = (
        attempts.filter(session_hash=session_hash, created_at__gte=burst_since).count() >= settings.UPLOAD_RATE_BURST_LIMIT
        or attempts.filter(session_hash=session_hash, created_at__gte=window_since).count() >= settings.UPLOAD_RATE_WINDOW_LIMIT
        or attempts.filter(ip_hash=ip_hash, created_at__gte=window_since).count() >= settings.UPLOAD_RATE_IP_LIMIT
    )
    return limited, session_hash, ip_hash


def record_upload_attempt(event, session_hash, ip_hash):
    UploadAttempt.objects.create(event=event, session_hash=session_hash, ip_hash=ip_hash)
    cutoff = timezone.now() - timedelta(seconds=settings.UPLOAD_RATE_WINDOW_SECONDS * 2)
    if UploadAttempt.objects.filter(created_at__lt=cutoff).count() > 500:
        UploadAttempt.objects.filter(created_at__lt=cutoff).delete()
