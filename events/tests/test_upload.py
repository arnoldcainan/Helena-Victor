import tempfile
from unittest.mock import patch

from cloudinary.exceptions import Error as CloudinaryError
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from events.models import Event, Photo, UploadAttempt
from .helpers import TEST_STORAGES, image_upload


class UploadTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name, STORAGES=TEST_STORAGES)
        self.settings_override.enable()
        self.event = Event.objects.create(name="Helena & Victor", slug="wedding", date="2026-10-03")
        self.url = reverse("upload-photo", args=[self.event.slug])

    def tearDown(self):
        self.settings_override.disable()
        self.temp_media.cleanup()

    def post(self, image=None, **data):
        payload = {"guest_name": "Ana", "caption": "Que dia lindo", "category": "party"}
        payload.update(data)
        if image is not None:
            payload["image"] = image
        return self.client.post(self.url, payload, HTTP_HX_REQUEST="true")

    def test_valid_jpeg_upload(self):
        response = self.post(image_upload())
        self.assertEqual(response.status_code, 200)
        photo = Photo.objects.get()
        self.assertEqual(photo.guest_name, "Ana")
        self.assertEqual(photo.category, "party")

    def test_valid_png_with_optional_fields_empty(self):
        response = self.post(image_upload("photo.png", "PNG"), guest_name="", caption="", category="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Photo.objects.get().caption, "")

    @override_settings(AUTO_APPROVE_UPLOADS=False)
    def test_auto_approval_can_be_disabled(self):
        response = self.post(image_upload())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Photo.objects.get().is_approved)

    def test_text_renamed_as_jpeg_is_rejected(self):
        fake = SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")
        response = self.post(fake)
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Não conseguimos processar", status_code=422)
        self.assertContains(response, "Ana", status_code=422)
        self.assertContains(response, "Que dia lindo", status_code=422)

    def test_false_mime_is_rejected(self):
        response = self.post(image_upload(content_type="text/plain"))
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "não corresponde", status_code=422)

    def test_corrupted_image_is_rejected(self):
        valid = image_upload().read()
        corrupt = SimpleUploadedFile("broken.jpg", valid[:40], content_type="image/jpeg")
        response = self.post(corrupt)
        self.assertEqual(response.status_code, 422)

    def test_empty_file_is_rejected(self):
        response = self.post(SimpleUploadedFile("empty.jpg", b"", content_type="image/jpeg"))
        self.assertEqual(response.status_code, 422)

    @override_settings(MAX_UPLOAD_SIZE_MB=0)
    def test_file_above_limit_is_rejected(self):
        response = self.post(image_upload())
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "no máximo", status_code=422)

    @override_settings(MAX_IMAGE_PIXELS=100)
    def test_excessive_pixel_count_is_rejected(self):
        response = self.post(image_upload(size=(20, 20)))
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "resolução", status_code=422)

    @override_settings(UPLOAD_RATE_BURST_LIMIT=1, UPLOAD_RATE_WINDOW_LIMIT=10, UPLOAD_RATE_IP_LIMIT=20)
    def test_rate_limit_returns_429(self):
        self.assertEqual(self.post(image_upload()).status_code, 200)
        response = self.post(image_upload("second.jpg"))
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_unknown_event_returns_404(self):
        url = reverse("upload-photo", args=["missing"])
        self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_cloudinary_failure_returns_503_without_incomplete_photo(self):
        storage = Photo._meta.get_field("image").storage
        with patch.object(storage, "save", side_effect=CloudinaryError("simulated storage failure")):
            response = self.post(image_upload(), guest_name="Nome preservado", caption="Legenda preservada")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Photo.objects.exists())
        self.assertContains(response, "Não conseguimos guardar", status_code=503)
        self.assertContains(response, "Nome preservado", status_code=503)
        self.assertContains(response, "Legenda preservada", status_code=503)

    def test_database_failure_after_storage_upload_deletes_orphan(self):
        storage = Photo._meta.get_field("image").storage

        def save_file_then_fail(instance, *args, **kwargs):
            if instance.image and not instance.image._committed:
                instance.image.save(instance.image.name, instance.image.file, save=False)
            raise DatabaseError("simulated insert failure")

        with (
            patch.object(storage, "save", return_value="wedding/audit.jpg"),
            patch.object(storage, "delete") as delete,
            patch.object(Photo, "save", save_file_then_fail),
        ):
            response = self.post(image_upload())
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Photo.objects.exists())
        delete.assert_called_once_with("wedding/audit.jpg")
