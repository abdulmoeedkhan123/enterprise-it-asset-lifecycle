from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Asset, LifecycleEvent, LifecycleStatus
from .services import transition_asset


class AssetLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="asset-operator",
            password="test-password",
        )
        self.view_permission = Permission.objects.get(
            content_type__app_label="inventory",
            codename="view_asset",
        )
        self.transition_permission = Permission.objects.get(
            content_type__app_label="inventory",
            codename="transition_asset",
        )
        self.client.force_login(self.user)

    def create_asset(self, **overrides):
        values = {
            "asset_id": "AST-1001",
            "asset_type": "Laptop",
            "manufacturer": "Example",
            "model": "Business Laptop",
            "site": "Sydney",
            "department": "IT",
            "lifecycle_status": LifecycleStatus.ASSIGNED,
            "custodian_ref": "EMP-1001",
            "purchase_date": date(2024, 1, 1),
            "warranty_end": date(2027, 1, 1),
            "source_last_updated": date(2026, 1, 1),
        }
        values.update(overrides)
        asset = Asset(**values)
        asset.full_clean()
        asset.save()
        return asset

    def test_authenticated_user_without_permission_is_forbidden(self):
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("inventory:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_shows_disposed_asset_missing_disposal_evidence(self):
        self.user.user_permissions.add(self.view_permission)
        asset = Asset.objects.create(
            asset_id="AST-1001",
            asset_type="Laptop",
            manufacturer="Example",
            model="Business Laptop",
            site="Sydney",
            department="IT",
            lifecycle_status=LifecycleStatus.DISPOSED,
            purchase_date=date(2024, 1, 1),
            warranty_end=date(2027, 1, 1),
            source_last_updated=date(2026, 1, 1),
            disposal_evidence_ref="",
        )

        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, asset.asset_id)
        self.assertContains(response, "Disposal evidence missing")

    def test_allowed_transition_updates_asset_and_writes_event(self):
        self.user.user_permissions.add(self.transition_permission)
        asset = self.create_asset()

        updated = transition_asset(
            asset_id=asset.pk,
            to_status=LifecycleStatus.RETURN_PENDING,
            actor=self.user,
            reason="Employee departure",
            return_due_date=timezone.localdate() + timedelta(days=7),
        )

        self.assertEqual(updated.lifecycle_status, LifecycleStatus.RETURN_PENDING)
        event = LifecycleEvent.objects.get(asset=asset)
        self.assertEqual(event.from_status, LifecycleStatus.ASSIGNED)
        self.assertEqual(event.to_status, LifecycleStatus.RETURN_PENDING)
        self.assertEqual(event.actor, self.user)

    def test_invalid_transition_does_not_change_asset_or_create_event(self):
        asset = self.create_asset()

        with self.assertRaises(ValidationError):
            transition_asset(
                asset_id=asset.pk,
                to_status=LifecycleStatus.DISPOSED,
                actor=self.user,
                reason="Invalid direct disposal",
                disposal_evidence_ref="DISP-1",
            )

        asset.refresh_from_db()
        self.assertEqual(asset.lifecycle_status, LifecycleStatus.ASSIGNED)
        self.assertFalse(LifecycleEvent.objects.filter(asset=asset).exists())

    def test_disposal_requires_evidence(self):
        asset = self.create_asset(
            custodian_ref="",
        )
        asset.lifecycle_status = LifecycleStatus.DISPOSED
        asset.disposal_evidence_ref = ""

        with self.assertRaises(ValidationError) as raised:
            asset.full_clean()

        self.assertIn("disposal_evidence_ref", raised.exception.message_dict)
