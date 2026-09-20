import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from events.models import Event, Photo, Reaction
from .helpers import TEST_STORAGES


class ReactionAndSecurityTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name, STORAGES=TEST_STORAGES)
        self.settings_override.enable()
        self.event = Event.objects.create(name="Wedding", slug="wedding", date="2026-10-03")
        self.photo = Photo(event=self.event)
        self.photo.image.save("photo.jpg", ContentFile(b"x"), save=True)
        self.react_url = reverse("react", args=[self.photo.pk])

    def tearDown(self):
        self.settings_override.disable()
        self.temp_media.cleanup()

    def test_add_and_remove_reaction(self):
        self.client.post(self.react_url, {"emoji": "heart"})
        self.assertEqual(Reaction.objects.count(), 1)
        self.client.post(self.react_url, {"emoji": "heart"})
        self.assertEqual(Reaction.objects.count(), 0)

    def test_different_emojis_can_coexist(self):
        self.client.post(self.react_url, {"emoji": "heart"})
        self.client.post(self.react_url, {"emoji": "sparkle"})
        self.assertEqual(Reaction.objects.count(), 2)

    def test_sessions_are_isolated_and_counts_are_independent(self):
        other = Client()
        self.client.post(self.react_url, {"emoji": "heart"})
        other.post(self.react_url, {"emoji": "heart"})
        other.post(self.react_url, {"emoji": "love"})
        response = self.client.get(reverse("event-detail", args=[self.event.slug]))
        card = response.context["photos"][0]
        self.assertEqual(card.heart_count, 2)
        self.assertEqual(card.love_count, 1)
        self.assertEqual(card.sparkle_count, 0)
        self.assertIn("heart", card.reacted_emojis)
        self.assertNotIn("love", card.reacted_emojis)

    def test_protected_endpoints_require_login(self):
        self.assertEqual(self.client.get(reverse("couple-dashboard")).status_code, 302)
        self.assertEqual(self.client.get(reverse("qrcode", args=[self.event.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("download-photo", args=[self.photo.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("download-album", args=[self.event.pk])).status_code, 302)

    def test_authenticated_downloads(self):
        user = get_user_model().objects.create_user("couple", password="secret")
        self.client.force_login(user)
        response = self.client.get(reverse("download-photo", args=[self.photo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        response.close()

        archive = self.client.get(reverse("download-album", args=[self.event.pk]))
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive["Content-Type"], "application/zip")
        archive.close()

    def test_share_url_points_to_public_event(self):
        response = self.client.get(reverse("share-text", args=[self.event.slug]))
        self.assertTrue(response.json()["url"].endswith("/e/wedding/"))
        self.assertNotIn("/share/", response.json()["url"])
