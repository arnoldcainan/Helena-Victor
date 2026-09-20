import base64
import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class ContentSecurityPolicyTests(TestCase):
    def policy_map(self, value):
        result = {}
        for directive in value.split(";"):
            parts = directive.strip().split()
            if parts:
                result[parts[0]] = parts[1:]
        return result

    @override_settings(CSP_ENABLED=True, CSP_REPORT_ONLY=False)
    def test_enforced_header_contains_required_directives(self):
        response = self.client.get(reverse("home"))
        self.assertIn("Content-Security-Policy", response)
        policy = self.policy_map(response["Content-Security-Policy"])
        self.assertEqual(policy["default-src"], ["'self'"])
        self.assertEqual(policy["object-src"], ["'none'"])
        self.assertEqual(policy["base-uri"], ["'self'"])
        self.assertEqual(policy["frame-ancestors"], ["'none'"])
        self.assertEqual(policy["form-action"], ["'self'"])

    @override_settings(CSP_ENABLED=True, CSP_REPORT_ONLY=True)
    def test_report_only_mode_uses_report_only_header(self):
        response = self.client.get(reverse("home"))
        self.assertIn("Content-Security-Policy-Report-Only", response)
        self.assertNotIn("Content-Security-Policy", response)

    @override_settings(CSP_ENABLED=False)
    def test_csp_can_be_disabled_explicitly(self):
        response = self.client.get(reverse("home"))
        self.assertNotIn("Content-Security-Policy", response)
        self.assertNotIn("Content-Security-Policy-Report-Only", response)

    def test_external_hosts_are_scoped_to_required_directives(self):
        policy = settings.CSP_DIRECTIVES
        self.assertEqual(policy["script-src"], ("'self'",))
        self.assertIn("https://fonts.googleapis.com", policy["style-src"])
        self.assertIn("https://fonts.gstatic.com", policy["font-src"])
        self.assertIn("https://res.cloudinary.com", policy["img-src"])
        self.assertNotIn("https://res.cloudinary.com", policy["connect-src"])

    def test_data_and_blob_are_limited_to_images(self):
        for directive, sources in settings.CSP_DIRECTIVES.items():
            if directive == "img-src":
                self.assertIn("data:", sources)
                self.assertIn("blob:", sources)
            else:
                self.assertNotIn("data:", sources)
                self.assertNotIn("blob:", sources)

    def test_policy_has_no_unsafe_or_broad_sources(self):
        sources = [source for values in settings.CSP_DIRECTIVES.values() for source in values]
        self.assertNotIn("'unsafe-eval'", sources)
        self.assertNotIn("'unsafe-inline'", sources)
        self.assertNotIn("*", sources)
        self.assertNotIn("https:", sources)
        self.assertEqual(settings.CSP_DIRECTIVES["script-src-attr"], ("'none'",))
        self.assertEqual(settings.CSP_DIRECTIVES["style-src-attr"], ("'none'",))

    def test_htmx_is_local_fixed_version_with_verified_subresource_integrity(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "/static/vendor/htmx-2.0.4.min.js")
        self.assertContains(response, "integrity=\"sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+\"")
        self.assertContains(response, "crossorigin=\"anonymous\"")
        self.assertContains(response, 'content=\'{"includeIndicatorStyles":false,"allowEval":false,"allowScriptTags":false}\'')
        htmx_path = Path(settings.BASE_DIR) / "static" / "vendor" / "htmx-2.0.4.min.js"
        digest = base64.b64encode(hashlib.sha384(htmx_path.read_bytes()).digest()).decode()
        self.assertEqual(digest, "HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+")
        self.assertNotContains(response, "onclick=")


class AdminCspCompatibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("audit-admin", "audit@example.invalid", "secret")
        self.client.force_login(self.user)

    @override_settings(CSP_ENABLED=True, CSP_REPORT_ONLY=False)
    def test_admin_core_pages_have_enforced_csp_and_no_inline_code(self):
        urls = [
            reverse("admin:index"),
            reverse("admin:events_event_changelist"),
            reverse("admin:events_event_add"),
            reverse("admin:events_photo_changelist") + "?q=guest&is_approved__exact=1",
            reverse("admin:events_reaction_changelist"),
        ]
        inline_script = re.compile(rb"<script(?![^>]*\bsrc=)[^>]*>", re.I)
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn("Content-Security-Policy", response)
                self.assertIsNone(inline_script.search(response.content))
                self.assertNotIn(b" onclick=", response.content.lower())
                self.assertNotIn(b" style=", response.content.lower())
