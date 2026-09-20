import tempfile
from pathlib import Path
from unittest.mock import patch

from cloudinary.exceptions import Error as CloudinaryError
from django.core.files.base import ContentFile
from django.test import TransactionTestCase, override_settings

from events.models import Event, Photo
from .helpers import TEST_STORAGES


class StoredFileDeletionTests(TransactionTestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name, STORAGES=TEST_STORAGES)
        self.settings_override.enable()
        self.event = Event.objects.create(name="Wedding", slug="storage-delete", date="2026-10-03")

    def tearDown(self):
        self.settings_override.disable()
        self.temp_media.cleanup()

    def create_photo(self):
        photo = Photo(event=self.event)
        photo.image.save("audit.jpg", ContentFile(b"stored-file"), save=True)
        return photo

    def test_deleting_photo_removes_file_after_commit(self):
        photo = self.create_photo()
        stored_path = Path(photo.image.path)
        self.assertTrue(stored_path.exists())
        photo.delete()
        self.assertFalse(stored_path.exists())

    def test_storage_delete_failure_does_not_restore_database_row(self):
        photo = self.create_photo()
        pk = photo.pk
        storage = photo.image.storage
        with (
            patch.object(storage, "delete", side_effect=CloudinaryError("simulated delete failure")),
            self.assertLogs("events.models", level="WARNING"),
        ):
            photo.delete()
        self.assertFalse(Photo.objects.filter(pk=pk).exists())
