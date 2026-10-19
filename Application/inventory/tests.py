import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .integrations.scim import SCIMClient, SCIMError, SCIMIdentity
from .models import (
    Asset,
    IdentityLink,
    IntegrationRun,
    LifecycleEvent,
    LifecycleStatus,
    ReturnWorkItem,
)
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
        asset = self.create_asset()
        asset.lifecycle_status = LifecycleStatus.DISPOSED
        asset.disposal_evidence_ref = ""

        with self.assertRaises(ValidationError) as raised:
            asset.full_clean()

        self.assertIn("disposal_evidence_ref", raised.exception.message_dict)

    def test_return_work_queue_requires_its_view_permission(self):
        response = self.client.get(reverse("inventory:return-work-queue"))
        self.assertEqual(response.status_code, 403)

    def test_return_work_queue_lists_authorized_items(self):
        self.user.user_permissions.add(
            self.view_permission,
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="view_returnworkitem",
            ),
        )
        asset = self.create_asset()
        ReturnWorkItem.objects.create(
            asset=asset,
            source_provider="scim",
            source_event_id="scim-inactive:test",
            custodian_ref=asset.custodian_ref,
        )

        response = self.client.get(reverse("inventory:return-work-queue"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, asset.asset_id)
        self.assertContains(response, "Pending review")


class SCIMClientTests(TestCase):
    @staticmethod
    def response(payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        return response

    def test_scim_client_requests_only_id_and_active_and_follows_pages(self):
        first_page = self.response(
            {
                "totalResults": 2,
                "Resources": [{"id": "subject-1", "active": False}],
            }
        )
        second_page = self.response(
            {
                "totalResults": 2,
                "Resources": [{"id": "subject-2", "active": True}],
            }
        )
        with patch(
            "inventory.integrations.scim.urlopen",
            side_effect=[first_page, second_page],
        ) as mocked_urlopen:
            users = SCIMClient(
                base_url="https://idp.example/scim/v2",
                bearer_token="test-token",
                page_size=1,
            ).list_users()

        self.assertEqual(
            users,
            [
                SCIMIdentity(subject_id="subject-1", active=False),
                SCIMIdentity(subject_id="subject-2", active=True),
            ],
        )
        first_request = mocked_urlopen.call_args_list[0].args[0]
        self.assertIn("attributes=id%2Cactive", first_request.full_url)
        self.assertNotIn("email", first_request.full_url)
        self.assertEqual(
            first_request.get_header("Authorization"),
            "Bearer test-token",
        )
        self.assertEqual(mocked_urlopen.call_count, 2)

    def test_scim_client_rejects_non_https_and_embedded_credentials(self):
        for base_url in ("http://idp.example/scim/v2", "https://user:pass@idp.example"):
            with self.subTest(base_url=base_url), self.assertRaises(SCIMError):
                SCIMClient(base_url=base_url, bearer_token="test-token")


class SCIMSyncCommandTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            asset_id="AST-2001",
            asset_type="Laptop",
            manufacturer="Example",
            model="Business Laptop",
            site="Melbourne",
            department="IT",
            custodian_ref="EMP-2001",
            lifecycle_status=LifecycleStatus.ASSIGNED,
            purchase_date=date(2024, 1, 1),
            warranty_end=date(2027, 1, 1),
            source_last_updated=date(2026, 1, 1),
        )
        IdentityLink.objects.create(
            provider="scim",
            external_subject_id="subject-2001",
            custodian_ref="EMP-2001",
        )

    @patch.dict(
        "os.environ",
        {
            "SCIM_BASE_URL": "https://idp.example/scim/v2",
            "SCIM_BEARER_TOKEN": "test-token",
        },
    )
    @patch("inventory.management.commands.sync_scim_deactivations.SCIMClient.list_users")
    def test_sync_creates_idempotent_review_work_item_without_state_changes(
        self, list_users
    ):
        list_users.return_value = [
            SCIMIdentity(subject_id="subject-2001", active=False),
            SCIMIdentity(subject_id="unmapped-subject", active=False),
            SCIMIdentity(subject_id="active-subject", active=True),
        ]

        call_command("sync_scim_deactivations", confirm_read_only_authorized=True)
        call_command("sync_scim_deactivations", confirm_read_only_authorized=True)

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.lifecycle_status, LifecycleStatus.ASSIGNED)
        self.assertEqual(ReturnWorkItem.objects.count(), 1)
        self.assertEqual(
            ReturnWorkItem.objects.get().custodian_ref,
            "EMP-2001",
        )
        successful_runs = IntegrationRun.objects.filter(
            status=IntegrationRun.Status.SUCCEEDED
        ).order_by("pk")
        self.assertEqual(successful_runs.count(), 2)
        first_run, second_run = successful_runs
        self.assertEqual(first_run.work_items_created, 1)
        self.assertEqual(first_run.work_items_existing, 0)
        self.assertEqual(first_run.identities_unmatched, 1)
        self.assertEqual(second_run.work_items_created, 0)
        self.assertEqual(second_run.work_items_existing, 1)

    def test_sync_requires_explicit_authorization(self):
        with self.assertRaises(CommandError):
            call_command("sync_scim_deactivations")
        self.assertFalse(IntegrationRun.objects.exists())

    @patch.dict(
        "os.environ",
        {
            "SCIM_BASE_URL": "https://idp.example/scim/v2",
            "SCIM_BEARER_TOKEN": "test-token",
        },
    )
    @patch(
        "inventory.management.commands.sync_scim_deactivations.SCIMClient.list_users",
        side_effect=SCIMError("SCIM request failed with HTTP 503."),
    )
    def test_sync_records_failure_without_exposing_credentials(self, _list_users):
        with self.assertRaises(CommandError):
            call_command(
                "sync_scim_deactivations",
                confirm_read_only_authorized=True,
            )

        run = IntegrationRun.objects.get()
        self.assertEqual(run.status, IntegrationRun.Status.FAILED)
        self.assertNotIn("test-token", run.error_summary)

    def test_return_work_item_sets_and_clears_closed_timestamp(self):
        item = ReturnWorkItem.objects.create(
            asset=self.asset,
            source_provider="scim",
            source_event_id="scim-inactive:closed-state",
            custodian_ref=self.asset.custodian_ref,
        )
        item.status = ReturnWorkItem.Status.CLOSED
        item.save(update_fields=("status",))
        item.refresh_from_db()
        self.assertIsNotNone(item.closed_at)

        item.status = ReturnWorkItem.Status.OPEN
        item.save(update_fields=("status",))
        item.refresh_from_db()
        self.assertIsNone(item.closed_at)
