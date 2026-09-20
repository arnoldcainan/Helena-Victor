import tempfile
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from events.models import Event, Photo
from .helpers import TEST_STORAGES


class GalleryTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name, STORAGES=TEST_STORAGES)
        self.settings_override.enable()
        self.event = Event.objects.create(name="One", slug="one", date="2026-10-03")
        self.other_event = Event.objects.create(name="Two", slug="two", date="2026-10-04")

    def tearDown(self):
        self.settings_override.disable()
        self.temp_media.cleanup()

    def photo(self, event=None, approved=True, category="", caption=""):
        photo = Photo(event=event or self.event, is_approved=approved, category=category, caption=caption)
        photo.image.save(f"{caption or 'photo'}.jpg", ContentFile(b"x"), save=True)
        return photo

    def test_only_approved_photos_from_event_appear(self):
        self.photo(caption="approved")
        self.photo(approved=False, caption="SECRET_REJECTED_CAPTION")
        self.photo(event=self.other_event, caption="OTHER_EVENT_CAPTION")
        response = self.client.get(reverse("event-detail", args=[self.event.slug]))
        self.assertContains(response, "approved")
        self.assertNotContains(response, "SECRET_REJECTED_CAPTION")
        self.assertNotContains(response, "OTHER_EVENT_CAPTION")

    def test_ordering_is_newest_first(self):
        older = self.photo(caption="older")
        newer = self.photo(caption="newer")
        Photo.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(hours=1))
        response = self.client.get(reverse("event-detail", args=[self.event.slug]))
        rendered_ids = [photo.id for photo in response.context["photos"]]
        self.assertLess(rendered_ids.index(newer.id), rendered_ids.index(older.id))

    def test_category_filter(self):
        self.photo(category="party", caption="party-photo")
        self.photo(category="family", caption="family-photo")
        response = self.client.get(reverse("photo-page", args=[self.event.slug]), {"category": "party"})
        self.assertContains(response, "party-photo")
        self.assertNotContains(response, "family-photo")

    def test_cursor_pagination_does_not_repeat_items(self):
        for index in range(22):
            self.photo(caption=f"photo-{index}")
        first = self.client.get(reverse("event-detail", args=[self.event.slug]))
        cursor = first.context["next_cursor"]
        second = self.client.get(reverse("photo-page", args=[self.event.slug]), {"before": cursor})
        first_ids = {photo.id for photo in first.context["photos"]}
        second_ids = {photo.id for photo in second.context["photos"]}
        self.assertTrue(cursor)
        self.assertFalse(first_ids & second_ids)

    def test_unapproved_photo_cannot_be_opened(self):
        photo = self.photo(approved=False)
        self.assertEqual(self.client.get(reverse("photo-detail", args=[photo.pk])).status_code, 404)

    def test_empty_gallery_has_cursor_for_update_polling(self):
        response = self.client.get(reverse("event-detail", args=[self.event.slug]))
        self.assertTrue(response.context["latest_cursor"])

    def test_update_endpoint_detects_new_photo(self):
        initial = self.client.get(reverse("event-detail", args=[self.event.slug]))
        self.photo(caption="new-arrival")
        response = self.client.get(reverse("photo-updates", args=[self.event.slug]), {"after": initial.context["latest_cursor"]})
        self.assertEqual(response.json()["count"], 1)

    def test_gallery_query_count_does_not_grow_per_photo(self):
        self.client.get(reverse("event-detail", args=[self.event.slug]))
        for index in range(10):
            self.photo(caption=f"query-{index}")
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("event-detail", args=[self.event.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 6)
