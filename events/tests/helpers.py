from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def image_upload(name="photo.jpg", image_format="JPEG", content_type=None, size=(64, 64)):
    buffer = BytesIO()
    Image.new("RGB", size, "#d7bea7").save(buffer, format=image_format)
    mime = content_type or {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format]
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=mime)
