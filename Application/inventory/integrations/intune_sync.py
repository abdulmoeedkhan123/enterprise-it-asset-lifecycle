from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from django.db import DatabaseError, transaction
from django.utils import timezone

from inventory.models import Asset, IntuneDevice, IntuneSyncRun

from .intune import IntuneError, IntuneGraphClient, ManagedDevice


def _normalized_serial(value: str) -> str:
    return value.strip().casefold()


def sync_managed_devices(
    devices: list[ManagedDevice],
    *,
    run: IntuneSyncRun,
    fetched_at: datetime | None = None,
) -> None:
    """Reconcile a complete Graph snapshot without updating asset-owned data."""
    fetched_at = fetched_at or timezone.now()
    graph_serial_counts = Counter(
        serial
        for device in devices
        if (serial := _normalized_serial(device.serial_number))
    )
    assets_by_serial: dict[str, list[Asset]] = defaultdict(list)
    for asset in Asset.objects.exclude(serial_ref="").only(
        "pk", "serial_ref", "asset_id"
    ):
        assets_by_serial[_normalized_serial(asset.serial_ref)].append(asset)

    matched_count = 0
    unmatched_count = 0
    duplicate_count = 0
    with transaction.atomic():
        for device in devices:
            serial = _normalized_serial(device.serial_number)
            candidates = assets_by_serial.get(serial, []) if serial else []
            matched_asset = None
            if serial and (
                graph_serial_counts[serial] > 1 or len(candidates) > 1
            ):
                match_status = IntuneDevice.MatchStatus.DUPLICATE
                match_detail = (
                    "Serial reference occurs more than once in Intune or the asset register."
                )
                duplicate_count += 1
            elif not candidates:
                match_status = IntuneDevice.MatchStatus.UNMATCHED
                match_detail = (
                    "Serial reference is missing."
                    if not serial
                    else "No asset has this exact serial reference."
                )
                unmatched_count += 1
            else:
                match_status = IntuneDevice.MatchStatus.MATCHED
                match_detail = "Unique exact serial-reference match."
                matched_asset = candidates[0]
                matched_count += 1

            IntuneDevice.objects.update_or_create(
                managed_device_id=device.managed_device_id,
                defaults={
                    "device_name": device.device_name,
                    "serial_number": device.serial_number,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "operating_system": device.operating_system,
                    "os_version": device.os_version,
                    "compliance_state": device.compliance_state,
                    "last_sync_at": device.last_sync_at,
                    "match_status": match_status,
                    "match_detail": match_detail,
                    "matched_asset": matched_asset,
                    "last_seen_run": run,
                    "fetched_at": fetched_at,
                },
            )

        run.status = IntuneSyncRun.Status.SUCCEEDED
        run.records_received = len(devices)
        run.devices_matched = matched_count
        run.devices_unmatched = unmatched_count
        run.devices_duplicate = duplicate_count
        run.completed_at = fetched_at
        run.save(
            update_fields=(
                "status",
                "records_received",
                "devices_matched",
                "devices_unmatched",
                "devices_duplicate",
                "completed_at",
            )
        )


def run_intune_sync(*, client: IntuneGraphClient | None = None) -> IntuneSyncRun:
    run = IntuneSyncRun.objects.create(status=IntuneSyncRun.Status.RUNNING)
    try:
        graph_client = client or IntuneGraphClient.from_environment()
        devices = graph_client.list_managed_devices()
        sync_managed_devices(devices, run=run)
    except Exception as error:
        run.status = IntuneSyncRun.Status.FAILED
        detail = str(error) if isinstance(error, IntuneError) else "Unexpected sync failure; previous successful snapshot remains authoritative."
        run.error_summary = f"{type(error).__name__}: {detail}"[:500]
        run.completed_at = timezone.now()
        run.save(update_fields=("status", "error_summary", "completed_at"))
        raise
    run.refresh_from_db()
    return run
