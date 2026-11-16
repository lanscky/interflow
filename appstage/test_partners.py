"""Partner catalogue and Django admin contracts, using synthetic local media."""

import base64
import tempfile

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .admin import PartnerAdminForm
from .models import Partner, User


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def logo_upload(name="partner.png", size=None):
    content = PNG if size is None else PNG + b"\0" * (size - len(PNG))
    return SimpleUploadedFile(name, content, content_type="image/png")


class TemporaryPartnerMediaMixin:
    def setUp(self):
        super().setUp()
        media_root = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=media_root))


class PartnerApiTests(TemporaryPartnerMediaMixin, APITestCase):
    def test_public_list_returns_all_active_partners_ordered_with_image_urls(self):
        last = Partner.objects.create(name="Dernier", image=logo_upload(), position=9)
        first = Partner.objects.create(name="Premier", image=logo_upload(), position=1)
        tied = Partner.objects.create(name="Second", image=logo_upload(), position=1)
        hidden = Partner.objects.create(
            name="Masqué", image=logo_upload(), position=0, is_active=False,
        )

        response = self.client.get("/api/partners/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual([item["id"] for item in response.data], [first.pk, tied.pk, last.pk])
        self.assertNotIn(hidden.pk, [item["id"] for item in response.data])
        self.assertEqual(set(response.data[0]), {"id", "name", "image"})
        self.assertEqual(response.data[0]["name"], first.name)
        self.assertEqual(
            response.data[0]["image"],
            response.wsgi_request.build_absolute_uri(first.image.url),
        )

    def test_empty_public_catalogue_is_an_empty_list(self):
        response = self.client.get("/api/partners/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_public_catalogue_ignores_an_expired_or_invalid_bearer_token(self):
        response = self.client.get(
            "/api/partners/", HTTP_AUTHORIZATION="Bearer invalid-expired-token",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_public_detail_hides_inactive_partner(self):
        active = Partner.objects.create(name="Visible", image=logo_upload())
        hidden = Partner.objects.create(name="Masqué", image=logo_upload(), is_active=False)

        visible_response = self.client.get(f"/api/partners/{active.pk}/")
        hidden_response = self.client.get(f"/api/partners/{hidden.pk}/")

        self.assertEqual(visible_response.status_code, status.HTTP_200_OK)
        self.assertEqual(visible_response.data["id"], active.pk)
        self.assertEqual(hidden_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_writes_are_forbidden_even_for_staff_superuser(self):
        partner = Partner.objects.create(name="Protégé", image=logo_upload())
        staff = User.objects.create_superuser(
            username="partner-admin", email="partner-admin@example.com", password="TestPassword123!",
        )
        for actor in (None, staff):
            self.client.force_authenticate(actor)
            for method, url, data in (
                ("post", "/api/partners/", {"name": "Intrus"}),
                ("patch", f"/api/partners/{partner.pk}/", {"name": "Altéré"}),
                ("delete", f"/api/partners/{partner.pk}/", {}),
            ):
                with self.subTest(actor="staff" if actor else "anonymous", method=method):
                    response = getattr(self.client, method)(url, data, format="json")
                    self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
                    partner.refresh_from_db()
                    self.assertEqual(partner.name, "Protégé")
                    self.assertEqual(Partner.objects.count(), 1)


class PartnerAdminFormTests(TemporaryPartnerMediaMixin, TestCase):
    def form(self, image):
        return PartnerAdminForm(
            data={"name": "Université Test", "position": 2, "is_active": True},
            files={"image": image},
        )

    def test_valid_image_is_saved_in_partner_media_directory(self):
        form = self.form(logo_upload())
        self.assertTrue(form.is_valid(), form.errors)
        partner = form.save()
        self.assertTrue(partner.image.name.startswith("partners/"))
        self.assertTrue(partner.image.storage.exists(partner.image.name))

    def test_disguised_non_image_is_rejected(self):
        image = SimpleUploadedFile("logo.png", b"not an image", content_type="image/png")
        form = self.form(image)
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)
        self.assertFalse(Partner.objects.exists())

    def test_image_is_required_on_creation(self):
        form = PartnerAdminForm(data={"name": "Sans logo", "position": 0})
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_image_at_five_megabyte_limit_is_accepted(self):
        form = self.form(logo_upload(size=MAX_IMAGE_BYTES))
        self.assertTrue(form.is_valid(), form.errors)

    def test_image_over_five_megabyte_limit_is_rejected(self):
        form = self.form(logo_upload(size=MAX_IMAGE_BYTES + 1))
        self.assertFalse(form.is_valid())
        self.assertIn("5 Mo", str(form.errors["image"]))
        self.assertFalse(Partner.objects.exists())


class PartnerAdminPermissionTests(TemporaryPartnerMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.partner = Partner.objects.create(name="Original", image=logo_upload())
        self.staff = User.objects.create_user(
            username="partner-staff", email="partner-staff@example.com",
            password="TestPassword123!", is_active=True, is_staff=True,
        )
        self.list_url = reverse("admin:appstage_partner_changelist")
        self.add_url = reverse("admin:appstage_partner_add")
        self.change_url = reverse("admin:appstage_partner_change", args=[self.partner.pk])
        self.delete_url = reverse("admin:appstage_partner_delete", args=[self.partner.pk])

    def grant(self, *codenames):
        self.staff.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="appstage", content_type__model="partner",
            codename__in=codenames,
        ))
        # Each request must evaluate the newly assigned permissions.
        self.client.force_login(self.staff)

    def test_anonymous_admin_requests_require_login(self):
        for url in (self.list_url, self.add_url, self.change_url, self.delete_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_302_FOUND)
                self.assertIn(reverse("admin:login"), response.url)

    def test_staff_without_partner_permissions_cannot_write_or_bulk_delete(self):
        self.client.force_login(self.staff)
        for url, data in (
            (self.add_url, {"name": "Intrus", "image": logo_upload(), "position": 0}),
            (self.change_url, {"name": "Altéré", "position": 0}),
            (self.delete_url, {"post": "yes"}),
            (self.list_url, {"action": "delete_selected", "_selected_action": [self.partner.pk], "post": "yes"}),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, data).status_code, status.HTTP_403_FORBIDDEN)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.name, "Original")
        self.assertEqual(Partner.objects.count(), 1)

    def test_add_permission_allows_creation_but_not_change_or_delete(self):
        self.grant("add_partner")
        response = self.client.post(self.add_url, {
            "name": "Nouveau", "image": logo_upload(), "position": 4, "is_active": "on", "_save": "Enregistrer",
        })
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        created = Partner.objects.get(name="Nouveau")
        self.assertTrue(created.image.storage.exists(created.image.name))
        self.assertEqual(self.client.post(self.change_url, {"name": "Altéré", "position": 0}).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url, {"post": "yes"}).status_code, 403)

    def test_change_permission_allows_editing_but_not_add_or_delete(self):
        self.grant("view_partner", "change_partner")
        response = self.client.post(self.change_url, {
            "name": "Modifié", "position": 7, "_save": "Enregistrer",
        })
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.name, "Modifié")
        self.assertEqual(self.partner.position, 7)
        self.assertFalse(self.partner.is_active)
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url, {"post": "yes"}).status_code, 403)

    def test_delete_permission_allows_individual_deletion(self):
        self.grant("view_partner", "delete_partner")
        response = self.client.post(self.delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertFalse(Partner.objects.filter(pk=self.partner.pk).exists())

    def test_bulk_delete_requires_delete_permission(self):
        self.grant("view_partner", "change_partner")
        payload = {"action": "delete_selected", "_selected_action": [self.partner.pk], "post": "yes"}
        denied = self.client.post(self.list_url, payload)
        self.assertEqual(denied.status_code, status.HTTP_200_OK)
        self.assertTrue(Partner.objects.filter(pk=self.partner.pk).exists())

        self.grant("delete_partner")
        allowed = self.client.post(self.list_url, payload)
        self.assertEqual(allowed.status_code, status.HTTP_302_FOUND)
        self.assertFalse(Partner.objects.filter(pk=self.partner.pk).exists())
