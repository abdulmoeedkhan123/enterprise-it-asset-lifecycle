import json
from datetime import date
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .integrations.intune import (
    GRAPH_API_ROOT,
    IntuneError,
    IntuneGraphClient,
    ManagedDevice,
)
from .integrations.intune_sync import run_intune_sync, sync_managed_devices
from .models import Asset, IntuneDevice, IntuneSyncRun, LifecycleStatus


def graph_device(device_id: str, serial: str = "", **values) -> dict:
    return {
        "id": device_id,
        "deviceName": f"Device {device_id}",
        "serialNumber": serial,
        "manufacturer": "Example",
        "model": "Managed laptop",
        "operatingSystem": "Windows",
        "osVersion": "11",
        "complianceState": "compliant",
        "lastSyncDateTime": "2026-10-20T01:02:03Z",
        **values,
    }


def managed_device(device_id: str, serial: str = "", **values) -> ManagedDevice:
    graph_value = graph_device(device_id, serial, **values)
    return IntuneGraphClient._parse_device(graph_value)


class IntuneGraphClientTests(TestCase):
    @staticmethod
    def response(payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        return response

    @patch("inventory.integrations.intune.urlopen")
    def test_lists_paginated_devices_using_graph_get_requests(self, mocked_urlopen):
        mocked_urlopen.side_effect = [
            self.response(
                {
                    "value": [graph_device("managed-1", "SER-1")],
                    "@odata.nextLink": (
                        f"{GRAPH_API_ROOT}/deviceManagement/managedDevices"
                        "?$skiptoken=page-2"
                    ),
                }
            ),
            self.response({"value": [graph_device("managed-2", "SER-2")]}),
        ]

        devices = IntuneGraphClient(access_token="access-token").list_managed_devices()

        self.assertEqual([device.managed_device_id for device in devices], ["managed-1", "managed-2"])
        self.assertTrue(all(call.args[0].method == "GET" for call in mocked_urlopen.call_args_list))
        self.assertEqual(
            mocked_urlopen.call_args_list[0].args[0].get_header("Authorization"),
            "Bearer access-token",
        )
        selected_fields = mocked_urlopen.call_args_list[0].args[0].full_url
        self.assertIn("%24select=id%2CdeviceName%2CserialNumber", selected_fields)
        self.assertNotIn("userPrincipalName", selected_fields)

    @patch("inventory.integrations.intune.urlopen")
    def test_rejects_duplicate_managed_device_ids(self, mocked_urlopen):
        mocked_urlopen.return_value = self.response(
            {"value": [graph_device("managed-1"), graph_device("managed-1")]}
        )
        with self.assertRaisesMessage(IntuneError, "duplicate managed-device ID"):
            IntuneGraphClient(access_token="access-token").list_managed_devices()

    @patch("inventory.integrations.intune.urlopen")
    def test_rejects_untrusted_graph_pagination_url_before_following_it(
        self, mocked_urlopen
    ):
        mocked_urlopen.return_value = self.response(
            {
                "value": [],
                "@odata.nextLink": (
                    "https://attacker.example/deviceManagement/managedDevices"
                    "?token=steal"
                ),
            }
        )
        with self.assertRaisesMessage(IntuneError, "unsafe"):
            IntuneGraphClient(access_token="access-token").list_managed_devices()
        self.assertEqual(mocked_urlopen.call_count, 1)

    @patch("inventory.integrations.intune.urlopen")
    def test_rejects_malformed_pagination_port_as_intune_error(self, mocked_urlopen):
        mocked_urlopen.return_value = self.response(
            {
                "value": [],
                "@odata.nextLink": (
                    "https://graph.microsoft.com:not-a-port/v1.0"
                    "/deviceManagement/managedDevices"
                ),
            }
        )
        with self.assertRaisesMessage(IntuneError, "unsafe"):
            IntuneGraphClient(access_token="access-token").list_managed_devices()
        self.assertEqual(mocked_urlopen.call_count, 1)

    @patch("inventory.integrations.intune.urlopen")
    def test_rejects_malformed_pagination_authority_as_intune_error(
        self, mocked_urlopen
    ):
        mocked_urlopen.return_value = self.response(
            {
                "value": [],
                "@odata.nextLink": (
                    "https://[invalid/v1.0/deviceManagement/managedDevices"
                ),
            }
        )
        with self.assertRaisesMessage(IntuneError, "unsafe"):
            IntuneGraphClient(access_token="access-token").list_managed_devices()
        self.assertEqual(mocked_urlopen.call_count, 1)

    @patch("inventory.integrations.intune.urlopen")
    def test_graph_http_failures_are_reported_without_response_body(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            f"{GRAPH_API_ROOT}/deviceManagement/managedDevices",
            403,
            "Forbidden",
            {},
            None,
        )
        with self.assertRaisesMessage(IntuneError, "HTTP 403"):
            IntuneGraphClient(access_token="access-token").list_managed_devices()

    def test_rejects_malformed_device_record_and_timestamp(self):
        for value in (
            {"id": "", "serialNumber": ""},
            graph_device("managed-1", "SER-1", lastSyncDateTime="not-a-date"),
            graph_device("managed-1", "SER-1", complianceState={"compliant": True}),
        ):
            with self.subTest(value=value), self.assertRaises(IntuneError):
                IntuneGraphClient._parse_device(value)

    @patch("inventory.integrations.intune.urlopen")
    def test_client_credentials_are_sent_only_to_authority_token_endpoint(
        self, mocked_urlopen
    ):
        mocked_urlopen.return_value = self.response(
            {"access_token": "test-access-token", "expires_in": 3600}
        )
        with patch.dict(
            "os.environ",
            {
                "INTUNE_TENANT_ID": "tenant.example",
                "INTUNE_CLIENT_ID": "client-id",
                "INTUNE_CLIENT_SECRET": "client-secret",
            },
        ):
            client = IntuneGraphClient.from_environment()

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(client.access_token, "test-access-token")
        self.assertEqual(request.method, "POST")
        self.assertIn("login.microsoftonline.com/tenant.example/", request.full_url)
        self.assertIn(b"client_secret=client-secret", request.data)
        self.assertNotIn("client-secret", request.full_url)


class IntuneSyncTests(TestCase):
    def create_asset(self, asset_id: str, serial_ref: str) -> Asset:
        return Asset.objects.create(
            asset_id=asset_id,
            asset_type="Laptop",
            manufacturer="Asset owner",
            model="Asset model",
            serial_ref=serial_ref,
            site="Sydney",
            department="IT",
            lifecycle_status=LifecycleStatus.IN_STOCK,
            purchase_date=date(2025, 1, 1),
            warranty_end=date(2027, 1, 1),
            source_last_updated=date(2026, 10, 20),
        )

    def test_matches_only_unique_serials_and_flags_duplicate_or_unmatched_devices(self):
        matching_asset = self.create_asset("AST-MATCH", " serial-1 ")
        self.create_asset("AST-DUP-1", "SER-DUP")
        self.create_asset("AST-DUP-2", "ser-dup")
        run = IntuneSyncRun.objects.create(status=IntuneSyncRun.Status.RUNNING)

        devices = [
            managed_device("managed-match", "SERIAL-1"),
            managed_device("managed-duplicate-1", "SER-DUP"),
            managed_device("managed-duplicate-2", " ser-dup "),
            managed_device("managed-unmatched", "SER-NO-ASSET"),
            managed_device("managed-no-serial"),
        ]
        sync_managed_devices(devices, run=run)

        run.refresh_from_db()
        matched = IntuneDevice.objects.get(managed_device_id="managed-match")
        self.assertEqual(matched.match_status, IntuneDevice.MatchStatus.MATCHED)
        self.assertEqual(matched.matched_asset, matching_asset)
        self.assertEqual(
            IntuneDevice.objects.filter(match_status=IntuneDevice.MatchStatus.DUPLICATE).count(),
            2,
        )
        self.assertEqual(
            IntuneDevice.objects.filter(match_status=IntuneDevice.MatchStatus.UNMATCHED).count(),
            2,
        )
        self.assertEqual(run.records_received, 5)
        self.assertEqual(run.devices_matched, 1)
        self.assertEqual(run.devices_duplicate, 2)
        self.assertEqual(run.devices_unmatched, 2)
        matching_asset.refresh_from_db()
        self.assertEqual(matching_asset.manufacturer, "Asset owner")
        self.assertEqual(matching_asset.model, "Asset model")

    def test_repeated_sync_updates_snapshot_without_creating_duplicate_rows(self):
        client = MagicMock()
        client.list_managed_devices.side_effect = [
            [managed_device("managed-1", "SER-1", deviceName="Initial name")],
            [managed_device("managed-1", "SER-1", deviceName="Updated name")],
        ]

        first_run = run_intune_sync(client=client)
        second_run = run_intune_sync(client=client)

        self.assertEqual(IntuneDevice.objects.count(), 1)
        device = IntuneDevice.objects.get(managed_device_id="managed-1")
        self.assertEqual(device.device_name, "Updated name")
        self.assertEqual(device.last_seen_run, second_run)
        self.assertNotEqual(first_run.pk, second_run.pk)
        self.assertEqual(second_run.status, IntuneSyncRun.Status.SUCCEEDED)

    def test_failed_sync_preserves_last_successful_device_snapshot(self):
        first_client = MagicMock()
        first_client.list_managed_devices.return_value = [
            managed_device("managed-1", "SER-1", deviceName="Saved device")
        ]
        successful_run = run_intune_sync(client=first_client)

        failed_client = MagicMock()
        failed_client.list_managed_devices.side_effect = IntuneError(
            "Microsoft Graph request failed with HTTP 429."
        )
        with self.assertRaises(IntuneError):
            run_intune_sync(client=failed_client)

        device = IntuneDevice.objects.get(managed_device_id="managed-1")
        failed_run = IntuneSyncRun.objects.exclude(pk=successful_run.pk).get()
        self.assertEqual(device.device_name, "Saved device")
        self.assertEqual(device.last_seen_run, successful_run)
        self.assertEqual(failed_run.status, IntuneSyncRun.Status.FAILED)
        self.assertIn("HTTP 429", failed_run.error_summary)

    def test_read_only_device_page_requires_django_permission(self):
        user = get_user_model().objects.create_user(username="intune-viewer")
        self.client.force_login(user)
        self.assertEqual(
            self.client.get(reverse("inventory:intune-devices")).status_code,
            403,
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="view_intunedevice",
            )
        )
        self.assertEqual(
            self.client.get(reverse("inventory:intune-devices")).status_code,
            200,
        )

    def test_sync_command_requires_explicit_authorization(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaisesMessage(CommandError, "--confirm-read-only-authorized"):
            call_command("sync_intune_devices")
        self.assertFalse(IntuneSyncRun.objects.exists())
