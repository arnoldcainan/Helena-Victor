from datetime import date
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from events.models import Event, Photo


def create_dummy_photo(event, is_approved=True):
    image_io = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(image_io, format="JPEG")
    image_file = SimpleUploadedFile("test.jpg", image_io.getvalue(), content_type="image/jpeg")
    return Photo.objects.create(
        event=event,
        image=image_file,
        guest_name="Convidado Teste",
        caption="Legenda Teste",
        is_approved=is_approved,
    )


class CoupleAccessAndModerationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.couple_user = User.objects.create_user("helena_victor", password="password123")
        self.other_user = User.objects.create_user("other_couple", password="password123")
        self.superuser = User.objects.create_superuser("admin", "admin@example.com", "admin123")

        self.event_a = Event.objects.create(
            name="Helena & Victor",
            slug="helena-e-victor",
            date=date(2026, 10, 3),
            welcome_text="Bem-vindos!",
        )
        self.event_a.users.add(self.couple_user)

        self.event_b = Event.objects.create(
            name="Outro Casamento",
            slug="outro-casamento",
            date=date(2026, 11, 15),
            welcome_text="Olá!",
        )
        self.event_b.users.add(self.other_user)

        self.photo_a = create_dummy_photo(self.event_a, is_approved=True)

    def test_anonymous_redirected_to_login(self):
        urls = [
            reverse("couple-dashboard"),
            reverse("download-photo", args=[self.photo_a.pk]),
            reverse("download-album", args=[self.event_a.pk]),
            reverse("qrcode", args=[self.event_a.pk]),
            reverse("toggle-photo-approval", args=[self.photo_a.pk]),
        ]
        for url in urls:
            response = self.client.get(url) if "toggle" not in url else self.client.post(url)
            self.assertEqual(response.status_code, 302, f"Expected 302 for {url}")
            self.assertIn("/login/", response.url)

    def test_couple_can_access_their_own_event_dashboard(self):
        self.client.force_login(self.couple_user)
        response = self.client.get(reverse("couple-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Helena & Victor")
        self.assertContains(response, "Convidado Teste")

    def test_couple_cannot_access_or_manage_unassigned_event(self):
        self.client.force_login(self.other_user)  # Not assigned to event_a

        # Cannot view event_a in dashboard
        response = self.client.get(f"{reverse('couple-dashboard')}?event={self.event_a.pk}")
        self.assertEqual(response.status_code, 403)

        # Cannot download photo from event_a
        response = self.client.get(reverse("download-photo", args=[self.photo_a.pk]))
        self.assertEqual(response.status_code, 403)

        # Cannot download album of event_a
        response = self.client.get(reverse("download-album", args=[self.event_a.pk]))
        self.assertEqual(response.status_code, 403)

        # Cannot view qrcode of event_a
        response = self.client.get(reverse("qrcode", args=[self.event_a.pk]))
        self.assertEqual(response.status_code, 403)

        # Cannot moderate photo in event_a
        response = self.client.post(reverse("toggle-photo-approval", args=[self.photo_a.pk]))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_access_all_events(self):
        self.client.force_login(self.superuser)

        response = self.client.get(f"{reverse('couple-dashboard')}?event={self.event_a.pk}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("qrcode", args=[self.event_a.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("download-photo", args=[self.photo_a.pk]))
        self.assertEqual(response.status_code, 200)

    def test_toggle_photo_approval_hides_and_restores_in_public_gallery(self):
        self.client.force_login(self.couple_user)

        # Initially, photo is approved and appears in public gallery
        gallery_response = self.client.get(reverse("photo-page", args=[self.event_a.slug]))
        self.assertEqual(gallery_response.status_code, 200)
        self.assertContains(gallery_response, f'data-photo="{self.photo_a.id}"')

        # Couple hides photo
        toggle_response = self.client.post(reverse("toggle-photo-approval", args=[self.photo_a.pk]))
        self.assertEqual(toggle_response.status_code, 200)
        self.photo_a.refresh_from_db()
        self.assertFalse(self.photo_a.is_approved)
        self.assertContains(toggle_response, "Ocultada da galeria")

        # Now public gallery does NOT include this photo
        gallery_response = self.client.get(reverse("photo-page", args=[self.event_a.slug]))
        self.assertEqual(gallery_response.status_code, 200)
        self.assertNotContains(gallery_response, f'data-photo="{self.photo_a.id}"')

        # Couple restores photo
        toggle_response = self.client.post(reverse("toggle-photo-approval", args=[self.photo_a.pk]))
        self.assertEqual(toggle_response.status_code, 200)
        self.photo_a.refresh_from_db()
        self.assertTrue(self.photo_a.is_approved)
        self.assertContains(toggle_response, "Visível na galeria")

        # Photo visible in public gallery again
        gallery_response = self.client.get(reverse("photo-page", args=[self.event_a.slug]))
        self.assertEqual(gallery_response.status_code, 200)
        self.assertContains(gallery_response, f'data-photo="{self.photo_a.id}"')

    def test_user_with_no_events_sees_graceful_empty_dashboard(self):
        unassigned_user = get_user_model().objects.create_user("orphan", password="password123")
        self.client.force_login(unassigned_user)
        response = self.client.get(reverse("couple-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum evento associado")

    def test_login_page_renders_with_password_toggle(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Área dos Noivos")
        self.assertContains(response, 'data-action="toggle-password"')
        self.assertContains(response, 'id="id_password"')

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": "helena_victor", "password": "password123"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel do Casal")
        self.assertTrue(response.context["user"].is_authenticated)

    def test_login_invalid_credentials_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": "helena_victor", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-alert")
        self.assertFalse(response.context["user"].is_authenticated)

    def test_authenticated_user_accessing_login_redirected(self):
        self.client.force_login(self.couple_user)
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("couple-dashboard"), response.url)

    def test_logout_clears_session_and_redirects(self):
        self.client.force_login(self.couple_user)
        response = self.client.post(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_navbar_displays_correct_links(self):
        # As guest:
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Área dos Noivos")
        self.assertNotContains(response, "nav-btn-logout")

        # As logged-in couple:
        self.client.force_login(self.couple_user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Painel do Casal")
        self.assertContains(response, "nav-btn-logout")

