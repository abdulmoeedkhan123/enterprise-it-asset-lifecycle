import csv
import json
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .integrations.scim import SCIMClient, SCIMError, SCIMIdentity
from .integrations.adapters import (
    AdapterConfigurationError,
    SCIMIdentityAdapter,
    create_identity_adapter,
)
from .integrations.contracts import IdentityStatus
from .models import (
    Asset,
    IdentityLink,
    ImportRun,
    IntegrationRun,
    LifecycleEvent,
    LifecycleStatus,
    MaintenanceWorkOrder,
    ProcurementEvent,
    ProcurementRequest,
    DisposalCase,
    DisposalEvent,
    ReturnWorkItem,
)
from .notifications import build_asset_notifications
from .reporting import build_asset_quality_report
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

    def test_dashboard_filters_operational_and_quality_reports(self):
        self.user.user_permissions.add(self.view_permission)
        self.create_asset(asset_id="AST-SYD", site="Sydney")
        self.create_asset(asset_id="AST-MEL", site="Melbourne")

        response = self.client.get(
            reverse("inventory:dashboard"),
            {"site": "Sydney", "status": LifecycleStatus.ASSIGNED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["asset_count"], 1)
        self.assertEqual(response.context["assigned_count"], 1)
        self.assertEqual(response.context["quality_report"]["asset_count"], 1)

    def test_notifications_show_due_and_expiring_assets_and_navigation_count(self):
        self.user.user_permissions.add(self.view_permission)
        today = timezone.localdate()
        self.create_asset(
            asset_id="AST-OVERDUE",
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date=today - timedelta(days=2),
            warranty_end=today + timedelta(days=90),
        )
        self.create_asset(
            asset_id="AST-WARRANTY-SOON",
            lifecycle_status=LifecycleStatus.IN_STOCK,
            custodian_ref="",
            warranty_end=today + timedelta(days=10),
        )

        response = self.client.get(reverse("inventory:notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Return overdue")
        self.assertContains(response, "Warranty expiring")
        self.assertEqual(len(response.context["notifications"]), 2)
        self.assertEqual(response.context["asset_notification_count"], 2)
        self.assertContains(response, "Notifications")

    def test_notifications_are_live_and_clear_when_asset_record_is_resolved(self):
        self.user.user_permissions.add(self.view_permission)
        today = timezone.localdate()
        asset = self.create_asset(
            asset_id="AST-RESOLVE-ALERT",
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date=today - timedelta(days=1),
            warranty_end=today + timedelta(days=90),
        )
        self.assertEqual(len(build_asset_notifications(as_of=today)), 1)

        asset.lifecycle_status = LifecycleStatus.ASSIGNED
        asset.return_due_date = None
        asset.save(update_fields=("lifecycle_status", "return_due_date"))
        response = self.client.get(reverse("inventory:notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You’re all caught up")
        self.assertEqual(response.context["asset_notification_count"], 0)

    def test_notifications_require_asset_view_permission(self):
        response = self.client.get(reverse("inventory:notifications"))

        self.assertEqual(response.status_code, 403)

    def test_notifications_are_paginated(self):
        self.user.user_permissions.add(self.view_permission)
        today = timezone.localdate()
        for index in range(51):
            self.create_asset(
                asset_id=f"AST-WARRANTY-{index:03}",
                lifecycle_status=LifecycleStatus.IN_STOCK,
                custodian_ref="",
                warranty_end=today + timedelta(days=10),
            )

        first_page = self.client.get(reverse("inventory:notifications"))
        second_page = self.client.get(
            reverse("inventory:notifications"),
            {"page": 2},
        )

        self.assertEqual(first_page.context["notification_page"].paginator.count, 51)
        self.assertEqual(len(first_page.context["notifications"]), 50)
        self.assertEqual(len(second_page.context["notifications"]), 1)

    def test_maintenance_work_order_create_and_status_history(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="view_maintenanceworkorder",
            ),
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="add_maintenanceworkorder",
            ),
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="change_maintenanceworkorder",
            ),
        )
        asset = self.create_asset()

        response = self.client.post(
            reverse("inventory:maintenance-work-order-create", args=[asset.pk]),
            {
                "title": "Replace damaged screen",
                "description": "Screen flickers during use.",
                "priority": MaintenanceWorkOrder.Priority.HIGH,
                "vendor": "Example Repairs",
                "target_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
                "cost": "180.00",
            },
        )

        self.assertRedirects(response, reverse("inventory:maintenance-work-orders"))
        work_order = MaintenanceWorkOrder.objects.get(asset=asset)
        self.assertEqual(work_order.status, MaintenanceWorkOrder.Status.OPEN)
        self.assertEqual(work_order.created_by, self.user)
        self.assertEqual(work_order.events.count(), 1)

        response = self.client.post(
            reverse(
                "inventory:maintenance-work-order-update",
                args=[work_order.pk],
            ),
            {"status": MaintenanceWorkOrder.Status.IN_PROGRESS},
        )

        self.assertRedirects(response, reverse("inventory:maintenance-work-orders"))
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, MaintenanceWorkOrder.Status.IN_PROGRESS)
        self.assertEqual(work_order.events.count(), 2)
        self.assertEqual(
            work_order.events.first().actor,
            self.user,
        )

        self.client.post(
            reverse(
                "inventory:maintenance-work-order-update",
                args=[work_order.pk],
            ),
            {"status": MaintenanceWorkOrder.Status.COMPLETED},
        )
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, MaintenanceWorkOrder.Status.COMPLETED)
        self.assertIsNotNone(work_order.completed_at)

        self.client.post(
            reverse(
                "inventory:maintenance-work-order-update",
                args=[work_order.pk],
            ),
            {"status": MaintenanceWorkOrder.Status.IN_PROGRESS},
        )
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, MaintenanceWorkOrder.Status.COMPLETED)

    def test_maintenance_work_orders_require_view_permission(self):
        response = self.client.get(reverse("inventory:maintenance-work-orders"))

        self.assertEqual(response.status_code, 403)

    def test_maintenance_work_order_cannot_be_created_for_disposed_asset(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="add_maintenanceworkorder",
            )
        )
        asset = self.create_asset(
            lifecycle_status=LifecycleStatus.DISPOSED,
            disposal_evidence_ref="DISP-REF",
        )

        response = self.client.get(
            reverse("inventory:maintenance-work-order-create", args=[asset.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("inventory:asset-detail", args=[asset.pk]),
        )
        self.assertFalse(MaintenanceWorkOrder.objects.exists())

    def test_procurement_quote_approval_order_delivery_and_receiving_workflow(self):
        add_permissions = [
            "view_purchaserequest",
            "add_purchaserequest",
            "change_purchaserequest",
            "add_asset",
            "view_asset",
            "approve_procurementrequest",
        ]
        self.user.user_permissions.add(
            *[
                Permission.objects.get(
                    content_type__app_label="inventory",
                    codename=codename,
                )
                for codename in add_permissions
            ]
        )
        required_by = timezone.localdate() + timedelta(days=20)
        response = self.client.post(
            reverse("inventory:procurement-create"),
            {
                "title": "Replacement laptops",
                "description": "Two standard laptops.",
                "justification": "Replace failed devices.",
                "quantity": 2,
                "required_by": required_by.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        purchase_request = ProcurementRequest.objects.get()

        for supplier, cost in (("Supplier A", "1200.00"), ("Supplier B", "1150.00")):
            self.client.post(
                reverse("inventory:procurement-quote-add", args=[purchase_request.pk]),
                {
                    "supplier": supplier,
                    "quote_reference": f"Q-{supplier[-1]}",
                    "unit_cost": cost,
                    "delivery_days": 8,
                    "notes": "Synthetic quote for testing.",
                },
            )
        selected_quote = purchase_request.quotes.get(supplier="Supplier B")
        self.client.post(
            reverse(
                "inventory:procurement-quote-select",
                args=[purchase_request.pk, selected_quote.pk],
            )
        )
        self.client.post(
            reverse("inventory:procurement-submit", args=[purchase_request.pk])
        )
        purchase_request.refresh_from_db()
        self.assertEqual(
            purchase_request.status,
            ProcurementRequest.Status.PENDING_APPROVAL,
        )

        self.client.post(
            reverse("inventory:procurement-review", args=[purchase_request.pk]),
            {"decision": "approve", "note": "Self approval must be blocked."},
        )
        purchase_request.refresh_from_db()
        self.assertEqual(
            purchase_request.status,
            ProcurementRequest.Status.PENDING_APPROVAL,
        )

        approver = get_user_model().objects.create_user(
            username="procurement-approver",
            password="test-only-password",
        )
        approver.user_permissions.add(
            *[
                Permission.objects.get(
                    content_type__app_label="inventory",
                    codename=codename,
                )
                for codename in (
                    "view_purchaserequest",
                    "approve_procurementrequest",
                    "manage_procurementrequest",
                )
            ]
        )
        self.client.force_login(approver)
        self.client.post(
            reverse("inventory:procurement-review", args=[purchase_request.pk]),
            {"decision": "approve", "note": "Approved for test."},
        )
        purchase_request.refresh_from_db()
        self.assertEqual(purchase_request.status, ProcurementRequest.Status.APPROVED)
        self.client.post(
            reverse("inventory:procurement-order", args=[purchase_request.pk]),
            {
                "purchase_order_reference": "PO-TEST-1",
                "expected_delivery_date": required_by.isoformat(),
                "tracking_reference": "TRACK-TEST",
            },
        )
        purchase_request.refresh_from_db()
        self.assertEqual(purchase_request.status, ProcurementRequest.Status.ORDERED)
        self.assertEqual(purchase_request.delivery_status, "ordered")
        self.client.post(
            reverse(
                "inventory:procurement-delivery-update",
                args=[purchase_request.pk],
            ),
            {
                "delivery_status": "in_transit",
                "expected_delivery_date": required_by.isoformat(),
                "tracking_reference": "TRACK-UPDATED",
            },
        )
        self.client.post(
            reverse("inventory:procurement-receive", args=[purchase_request.pk]),
            {"quantity": 1, "receipt_reference": "GRN-1"},
        )
        purchase_request.refresh_from_db()
        self.assertEqual(
            purchase_request.status,
            ProcurementRequest.Status.PARTIALLY_RECEIVED,
        )
        self.assertEqual(purchase_request.quantity_received, 1)
        self.assertEqual(purchase_request.delivery_status, "partially_received")

        self.client.force_login(self.user)
        asset_payload = {
            "asset_type": "Laptop",
            "manufacturer": "Example",
            "model": "Business Laptop",
            "site": "Sydney",
            "department": "IT",
            "custodian_ref": "",
            "purchase_date": timezone.localdate().isoformat(),
            "warranty_end": (timezone.localdate() + timedelta(days=365)).isoformat(),
            "return_due_date": "",
            "sanitisation_required": "",
            "sanitisation_result": "",
            "sanitisation_evidence_ref": "",
            "disposal_evidence_ref": "",
            "source_last_updated": timezone.localdate().isoformat(),
            "procurement_id": purchase_request.pk,
        }
        self.client.post(
            f"{reverse('inventory:asset-create')}?procurement_id={purchase_request.pk}",
            {**asset_payload, "asset_id": "AST-PROC-1", "serial_ref": "BAR-PROC-1"},
        )
        self.assertEqual(purchase_request.registered_assets.count(), 1)

        self.client.force_login(approver)
        self.client.post(
            reverse("inventory:procurement-receive", args=[purchase_request.pk]),
            {"quantity": 2, "receipt_reference": "GRN-OVER"},
        )
        purchase_request.refresh_from_db()
        self.assertEqual(purchase_request.quantity_received, 1)
        self.client.post(
            reverse("inventory:procurement-receive", args=[purchase_request.pk]),
            {"quantity": 1, "receipt_reference": "GRN-2"},
        )
        purchase_request.refresh_from_db()
        self.assertEqual(purchase_request.status, ProcurementRequest.Status.RECEIVED)
        self.assertEqual(purchase_request.delivery_status, "received")
        self.assertEqual(
            purchase_request.events.filter(
                event_type=ProcurementEvent.EventType.ASSET_REGISTERED
            ).count(),
            1,
        )
        self.assertEqual(purchase_request.events.count(), 11)

    def test_disposal_requires_independent_approval_and_evidence_to_complete(self):
        requester_permissions = [
            Permission.objects.get(
                content_type__app_label="inventory",
                codename=codename,
            )
            for codename in (
                "view_disposalcase",
                "add_disposalcase",
                "approve_disposalcase",
            )
        ]
        self.user.user_permissions.add(*requester_permissions)
        asset = self.create_asset(
            lifecycle_status=LifecycleStatus.READY_FOR_DISPOSAL,
            custodian_ref="",
        )
        self.client.post(
            reverse("inventory:disposal-create", args=[asset.pk]),
            {
                "reason": "End of supported life.",
                "method": DisposalCase.Method.RECYCLE,
                "sanitisation_result": "",
                "sanitisation_evidence_ref": "",
            },
        )
        case = DisposalCase.objects.get(asset=asset)
        self.assertEqual(case.status, DisposalCase.Status.PENDING_APPROVAL)
        self.client.post(
            reverse("inventory:disposal-review", args=[case.pk]),
            {"decision": "approve", "note": "Self approval."},
        )
        case.refresh_from_db()
        self.assertEqual(case.status, DisposalCase.Status.PENDING_APPROVAL)

        reviewer = get_user_model().objects.create_user(
            username="disposal-reviewer",
            password="test-only-password",
        )
        reviewer.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="approve_disposalcase",
            )
        )
        self.client.force_login(reviewer)
        self.client.post(
            reverse("inventory:disposal-review", args=[case.pk]),
            {"decision": "approve", "note": "Approved."},
        )
        case.refresh_from_db()
        self.assertEqual(case.status, DisposalCase.Status.APPROVED)

        executor = get_user_model().objects.create_user(
            username="disposal-executor",
            password="test-only-password",
        )
        executor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="complete_disposalcase",
            )
        )
        self.client.force_login(executor)
        self.client.post(
            reverse("inventory:disposal-complete", args=[case.pk]),
            {"disposal_evidence_ref": ""},
        )
        case.refresh_from_db()
        self.assertEqual(case.status, DisposalCase.Status.APPROVED)
        self.client.post(
            reverse("inventory:disposal-complete", args=[case.pk]),
            {"disposal_evidence_ref": "DISP-EVIDENCE-001"},
        )
        case.refresh_from_db()
        asset.refresh_from_db()
        self.assertEqual(case.status, DisposalCase.Status.COMPLETED)
        self.assertEqual(asset.lifecycle_status, LifecycleStatus.DISPOSED)
        self.assertEqual(asset.disposal_evidence_ref, "DISP-EVIDENCE-001")
        self.assertEqual(case.events.count(), 3)

    def test_disposal_request_requires_sanitisation_evidence_when_flagged(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="add_disposalcase",
            )
        )
        asset = self.create_asset(
            lifecycle_status=LifecycleStatus.READY_FOR_DISPOSAL,
            custodian_ref="",
            sanitisation_required=True,
            sanitisation_result="Passed",
            sanitisation_evidence_ref="SAN-READY-1",
        )
        response = self.client.post(
            reverse("inventory:disposal-create", args=[asset.pk]),
            {
                "reason": "Retire the asset.",
                "method": DisposalCase.Method.SECURE_DESTRUCTION,
                "sanitisation_result": "",
                "sanitisation_evidence_ref": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DisposalCase.objects.exists())

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

    def test_integration_catalog_distinguishes_available_from_unimplemented(self):
        self.user.user_permissions.add(self.view_permission)

        response = self.client.get(reverse("inventory:integration-catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SCIM 2.0 user status")
        self.assertContains(response, "Available - generic connector")
        self.assertContains(response, "Microsoft Entra ID / Microsoft Graph")
        self.assertContains(response, "Adapter required")
        self.assertContains(response, "Blancco")
        self.assertContains(response, "Blocked pending vendor contract")
        self.assertContains(response, "No external connection is enabled")


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

    def test_scim_adapter_normalizes_provider_records_to_shared_contract(self):
        client = MagicMock()
        client.list_users.return_value = [
            SCIMIdentity(subject_id="subject-1", active=False)
        ]

        adapter = SCIMIdentityAdapter(client=client)

        self.assertEqual(
            adapter.fetch_identity_statuses(),
            [IdentityStatus(subject_id="subject-1", active=False)],
        )

    def test_adapter_factory_rejects_unimplemented_provider(self):
        with patch.dict(
            "os.environ",
            {
                "SCIM_BASE_URL": "https://idp.example/scim/v2",
                "SCIM_BEARER_TOKEN": "test-token",
            },
        ):
            self.assertEqual(create_identity_adapter("scim").provider_id, "scim")
        with self.assertRaisesMessage(AdapterConfigurationError, "No verified adapter"):
            create_identity_adapter("entra")


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
    @patch("inventory.management.commands.sync_scim_deactivations.create_identity_adapter")
    def test_sync_creates_idempotent_review_work_item_without_state_changes(
        self, create_adapter
    ):
        adapter = create_adapter.return_value
        adapter.provider_id = "scim"
        adapter.fetch_identity_statuses.return_value = [
            IdentityStatus(subject_id="subject-2001", active=False),
            IdentityStatus(subject_id="unmapped-subject", active=False),
            IdentityStatus(subject_id="active-subject", active=True),
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
        "inventory.management.commands.sync_scim_deactivations.create_identity_adapter",
    )
    def test_sync_records_failure_without_exposing_credentials(self, create_adapter):
        create_adapter.return_value.fetch_identity_statuses.side_effect = SCIMError(
            "SCIM request failed with HTTP 503."
        )
        with self.assertRaises(CommandError):
            call_command(
                "sync_scim_deactivations",
                confirm_read_only_authorized=True,
            )

        run = IntegrationRun.objects.get()
        self.assertEqual(run.status, IntegrationRun.Status.FAILED)
        self.assertNotIn("test-token", run.error_summary)

    @patch(
        "inventory.management.commands.sync_scim_deactivations.create_identity_adapter",
        side_effect=SCIMError("SCIM request failed with HTTP 503."),
    )
    def test_configuration_failure_is_recorded(self, _create_adapter):
        with self.assertRaises(CommandError):
            call_command(
                "sync_scim_deactivations",
                confirm_read_only_authorized=True,
            )
        self.assertEqual(
            IntegrationRun.objects.get().status,
            IntegrationRun.Status.FAILED,
        )

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


class AssetImportPipelineTests(TestCase):
    headers = (
        "asset_id",
        "asset_type",
        "manufacturer",
        "model",
        "serial_ref",
        "site",
        "department",
        "custodian_ref",
        "lifecycle_status",
        "purchase_date",
        "warranty_end",
        "return_due_date",
        "sanitisation_required",
        "sanitisation_result",
        "sanitisation_evidence_ref",
        "disposal_evidence_ref",
        "last_updated",
    )

    def write_csv(self, path: Path, **overrides):
        row = {
            "asset_id": "AST-ETL-1",
            "asset_type": "Laptop",
            "manufacturer": "Example",
            "model": "Business Laptop",
            "serial_ref": "SER-ETL-1",
            "site": "Sydney",
            "department": "IT",
            "custodian_ref": "",
            "lifecycle_status": LifecycleStatus.IN_STOCK,
            "purchase_date": "2024-01-01",
            "warranty_end": "2027-01-01",
            "return_due_date": "",
            "sanitisation_required": "false",
            "sanitisation_result": "",
            "sanitisation_evidence_ref": "",
            "disposal_evidence_ref": "",
            "last_updated": "2026-10-18",
        }
        row.update(overrides)
        with path.open("w", newline="", encoding="utf-8") as source_file:
            writer = csv.DictWriter(source_file, fieldnames=self.headers)
            writer.writeheader()
            writer.writerow(row)

    def test_import_run_is_idempotent_and_persists_quality_profile(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "assets.csv"
            self.write_csv(path, asset_id="  AST-ETL-1  ")

            for _ in range(2):
                call_command(
                    "import_assets",
                    input=path,
                    confirm_authorized_source=True,
                    stdout=StringIO(),
                )

        self.assertEqual(Asset.objects.count(), 1)
        self.assertEqual(Asset.objects.get().asset_id, "AST-ETL-1")
        runs = list(ImportRun.objects.order_by("pk"))
        self.assertEqual(runs[0].rows_created, 1)
        self.assertEqual(runs[0].rows_unchanged, 0)
        self.assertEqual(runs[1].rows_created, 0)
        self.assertEqual(runs[1].rows_unchanged, 1)
        self.assertEqual(runs[1].rows_rejected, 0)
        self.assertEqual(runs[1].quality_summary["records_profiled"], 1)

    def test_import_quality_profile_counts_accepted_exception_rows(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "quality-assets.csv"
            self.write_csv(
                path,
                lifecycle_status=LifecycleStatus.ASSIGNED,
                custodian_ref="",
            )
            call_command(
                "import_assets",
                input=path,
                confirm_authorized_source=True,
                stdout=StringIO(),
            )

        run = ImportRun.objects.get()
        self.assertEqual(run.status, ImportRun.Status.SUCCEEDED)
        self.assertEqual(run.quality_summary["assigned_without_custodian"], 1)
        self.assertEqual(run.rows_rejected, 0)

    def test_invalid_batch_is_rejected_and_recorded_without_partial_load(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad-assets.csv"
            self.write_csv(path, lifecycle_status="Unknown status")

            with self.assertRaises(CommandError):
                call_command(
                    "import_assets",
                    input=path,
                    confirm_authorized_source=True,
                    stdout=StringIO(),
                )

        run = ImportRun.objects.get()
        self.assertEqual(run.status, ImportRun.Status.FAILED)
        self.assertEqual(run.rows_rejected, 1)
        self.assertFalse(Asset.objects.exists())

    def test_import_requires_authorization_before_opening_source(self):
        with self.assertRaisesMessage(CommandError, "--confirm-authorized-source"):
            call_command(
                "import_assets",
                input=Path("/not/a/real/source.csv"),
            )
        self.assertFalse(ImportRun.objects.exists())


class AssetQualityReportingTests(TestCase):
    def test_quality_report_counts_overlapping_issues_without_double_counting_assets(self):
        report_date = date(2026, 10, 19)
        shared_values = {
            "asset_type": "Laptop",
            "manufacturer": "Example",
            "model": "Business Laptop",
            "site": "Sydney",
            "department": "IT",
            "purchase_date": date(2025, 1, 1),
            "warranty_end": date(2024, 1, 1),
            "source_last_updated": report_date - timedelta(days=100),
        }
        Asset.objects.create(
            asset_id="AST-QUALITY-1",
            serial_ref="SER-DUP",
            lifecycle_status=LifecycleStatus.ASSIGNED,
            **shared_values,
        )
        Asset.objects.create(
            asset_id="AST-QUALITY-2",
            serial_ref="SER-DUP",
            lifecycle_status=LifecycleStatus.DISPOSED,
            sanitisation_required=True,
            sanitisation_result="Pending",
            **shared_values,
        )
        Asset.objects.create(
            asset_id="AST-QUALITY-3",
            serial_ref="SER-OK",
            lifecycle_status=LifecycleStatus.IN_STOCK,
            **shared_values,
        )

        report = build_asset_quality_report(Asset.objects.all(), as_of=report_date)
        check_counts = {check["code"]: check["count"] for check in report["checks"]}

        self.assertEqual(report["asset_count"], 3)
        self.assertEqual(report["assets_with_issues"], 3)
        self.assertEqual(check_counts["assigned_without_custodian"], 1)
        self.assertEqual(check_counts["disposition_missing_sanitisation_evidence"], 1)
        self.assertEqual(check_counts["disposed_without_evidence"], 1)
        self.assertEqual(check_counts["stale_source_records"], 3)
        self.assertEqual(check_counts["warranty_before_purchase"], 3)
        self.assertEqual(check_counts["duplicate_serial_assets"], 2)
