from io import BytesIO
from pathlib import Path
import zipfile

from PIL import ExifTags, Image, PngImagePlugin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from events.forms import PhotoForm
from events.models import Event, Photo
from .helpers import TEST_STORAGES


def jpeg_with_exif(orientation=1, include_private=False):
    image = Image.new("RGB", (40, 20), "red")
    exif = Image.Exif()
    exif[274] = orientation
    if include_private:
        exif[271] = "Private Camera Maker"
        exif[272] = "Secret Phone Model"
        exif[305] = "Tracking Software"
        exif[306] = "2026:10:03 18:30:00"
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        gps[1] = "S"
        gps[2] = (23.0, 33.0, 0.0)
        gps[3] = "W"
        gps[4] = (46.0, 38.0, 0.0)
    output = BytesIO()
    image.save(output, "JPEG", quality=98, exif=exif, icc_profile=b"test-icc-profile")
    return SimpleUploadedFile("phone.jpg", output.getvalue(), content_type="image/jpeg")


def sanitized(upload):
    form = PhotoForm(data={"guest_name": "", "caption": "", "category": ""}, files={"image": upload})
    assert form.is_valid(), form.errors
    result = form.cleaned_data["image"]
    result.seek(0)
    return result


def jpeg_with_private_app_segments():
    output = BytesIO()
    Image.new("RGB", (20, 10), "purple").save(output, "JPEG", quality=95, comment=b"PRIVATE-JPEG-COMMENT")
    jpeg = output.getvalue()
    xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>PRIVATE-XMP-GPS</x:xmpmeta>"
    iptc = b"Photoshop 3.0\x008BIM\x04\x04PRIVATE-IPTC-CAPTION"
    app1 = b"\xff\xe1" + (len(xmp) + 2).to_bytes(2, "big") + xmp
    app13 = b"\xff\xed" + (len(iptc) + 2).to_bytes(2, "big") + iptc
    return SimpleUploadedFile("private-location-family-home.jpg", jpeg[:2] + app1 + app13 + jpeg[2:], content_type="image/jpeg")


class ImagePrivacyTests(SimpleTestCase):
    def test_all_exif_orientations_are_applied_physically(self):
        expected = {
            1: (40, 20), 2: (40, 20), 3: (40, 20), 4: (40, 20),
            5: (20, 40), 6: (20, 40), 7: (20, 40), 8: (20, 40),
        }
        for orientation, dimensions in expected.items():
            with self.subTest(orientation=orientation):
                clean = sanitized(jpeg_with_exif(orientation))
                with Image.open(clean) as image:
                    self.assertEqual(image.size, dimensions)
                    self.assertNotIn(274, image.getexif())

    def test_gps_and_device_identifiers_are_removed(self):
        source = jpeg_with_exif(6, include_private=True)
        source_bytes = source.read()
        with Image.open(BytesIO(source_bytes)) as original:
            self.assertIn(ExifTags.IFD.GPSInfo, original.getexif())
            self.assertEqual(original.getexif().get(271), "Private Camera Maker")
        clean = sanitized(SimpleUploadedFile("phone.jpg", source_bytes, content_type="image/jpeg"))
        with Image.open(clean) as image:
            exif = image.getexif()
            self.assertFalse(exif)
            self.assertNotIn(ExifTags.IFD.GPSInfo, exif)
            self.assertNotIn(271, exif)
            self.assertNotIn(272, exif)
            self.assertNotIn(305, exif)
            self.assertNotIn(306, exif)
            self.assertEqual(image.size, (20, 40))

    def test_icc_profile_is_preserved_without_exif(self):
        clean = sanitized(jpeg_with_exif(1, include_private=True))
        with Image.open(clean) as image:
            self.assertEqual(image.info.get("icc_profile"), b"test-icc-profile")
            self.assertFalse(image.getexif())

    def test_png_text_metadata_is_removed(self):
        output = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("GPS", "23.5,-46.6")
        metadata.add_text("Software", "Private App")
        Image.new("RGBA", (20, 10), "blue").save(output, "PNG", pnginfo=metadata)
        clean = sanitized(SimpleUploadedFile("phone.png", output.getvalue(), content_type="image/png"))
        with Image.open(clean) as image:
            self.assertEqual(image.format, "PNG")
            self.assertNotIn("GPS", image.info)
            self.assertNotIn("Software", image.info)

    def test_webp_exif_is_removed_and_file_remains_valid(self):
        output = BytesIO()
        exif = Image.Exif()
        exif[271] = "Private Maker"
        xmp = b"<x:xmpmeta>PRIVATE-WEBP-XMP</x:xmpmeta>"
        Image.new("RGB", (20, 10), "green").save(output, "WEBP", quality=98, exif=exif, xmp=xmp)
        clean = sanitized(SimpleUploadedFile("phone.webp", output.getvalue(), content_type="image/webp"))
        clean_bytes = clean.read()
        self.assertNotIn(b"PRIVATE-WEBP-XMP", clean_bytes)
        clean.seek(0)
        with Image.open(clean) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertFalse(image.getexif())
            self.assertNotIn("xmp", image.info)
            image.verify()

    def test_jpeg_xmp_iptc_and_comments_are_removed(self):
        clean = sanitized(jpeg_with_private_app_segments())
        clean_bytes = clean.read()
        self.assertNotIn(b"PRIVATE-XMP-GPS", clean_bytes)
        self.assertNotIn(b"PRIVATE-IPTC-CAPTION", clean_bytes)
        self.assertNotIn(b"PRIVATE-JPEG-COMMENT", clean_bytes)
        with Image.open(BytesIO(clean_bytes)) as image:
            self.assertNotIn("xmp", image.info)
            self.assertFalse(image.getexif())

    def test_sanitized_filename_is_neutral_uuid_with_detected_extension(self):
        clean = sanitized(jpeg_with_private_app_segments())
        self.assertNotIn("private-location-family-home", clean.name)
        self.assertRegex(clean.name, r"^[0-9a-f]{32}\.jpg$")

    def test_png_alpha_is_preserved(self):
        output = BytesIO()
        image = Image.new("RGBA", (2, 1))
        image.putdata([(255, 0, 0, 0), (0, 0, 255, 128)])
        image.save(output, "PNG")
        clean = sanitized(SimpleUploadedFile("alpha.png", output.getvalue(), content_type="image/png"))
        with Image.open(clean) as result:
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((0, 0))[3], 0)
            self.assertEqual(result.getpixel((1, 0))[3], 128)

    def test_webp_alpha_is_preserved(self):
        output = BytesIO()
        image = Image.new("RGBA", (2, 1))
        image.putdata([(255, 0, 0, 0), (0, 255, 0, 255)])
        image.save(output, "WEBP", lossless=True)
        clean = sanitized(SimpleUploadedFile("alpha.webp", output.getvalue(), content_type="image/webp"))
        with Image.open(clean) as result:
            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.getpixel((0, 0))[3], 0)
            self.assertEqual(result.getpixel((1, 0))[3], 255)


class StoredImagePrivacyTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media.name, STORAGES=TEST_STORAGES)
        self.settings_override.enable()
        self.event = Event.objects.create(name="Wedding", slug="privacy", date="2026-10-03")

    def tearDown(self):
        self.settings_override.disable()
        self.temp_media.cleanup()

    def test_upload_stores_only_sanitized_oriented_file(self):
        response = self.client.post(
            reverse("upload-photo", args=[self.event.slug]),
            {"guest_name": "Ana", "caption": "Mobile", "image": jpeg_with_exif(6, include_private=True)},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        photo = Photo.objects.get()
        self.assertRegex(Path(photo.image.name).name, r"^[0-9a-f]{32}\.jpg$")
        self.assertNotIn("phone", photo.image.name)
        photo.image.open("rb")
        with Image.open(photo.image) as stored:
            self.assertEqual(stored.size, (20, 40))
            self.assertFalse(stored.getexif())
            self.assertIn(photo.image.url, response.content.decode())
        photo.image.close()

    def test_authenticated_downloads_reuse_the_sanitized_stored_file(self):
        self.client.post(
            reverse("upload-photo", args=[self.event.slug]),
            {"guest_name": "Ana", "caption": "Mobile", "image": jpeg_with_exif(6, include_private=True)},
            HTTP_HX_REQUEST="true",
        )
        photo = Photo.objects.get()
        user = get_user_model().objects.create_user("couple", password="secret")
        self.event.users.add(user)
        self.client.force_login(user)

        response = self.client.get(reverse("download-photo", args=[photo.pk]))
        downloaded = b"".join(response.streaming_content)
        response.close()
        self.assertNotIn(b"Private Camera Maker", downloaded)
        with Image.open(BytesIO(downloaded)) as image:
            self.assertEqual(image.size, (20, 40))
            self.assertFalse(image.getexif())

        response = self.client.get(reverse("download-album", args=[self.event.pk]))
        archive_bytes = b"".join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            self.assertEqual(len(archive.namelist()), 1)
            self.assertNotIn("phone", archive.namelist()[0])
            archived = archive.read(archive.namelist()[0])
        self.assertNotIn(b"Private Camera Maker", archived)
        with Image.open(BytesIO(archived)) as image:
            self.assertEqual(image.size, (20, 40))
            self.assertFalse(image.getexif())
