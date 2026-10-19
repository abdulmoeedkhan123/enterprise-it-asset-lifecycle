from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from .models import Asset, LifecycleStatus


def asset_notification_filter(*, as_of: date | None = None) -> Q:
    today = as_of or timezone.localdate()
    active_assets = ~Q(
        lifecycle_status__in=[LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN]
    )
    return (
        Q(lifecycle_status=LifecycleStatus.RETURN_PENDING, return_due_date__lt=today)
        | Q(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__range=(today, today + timedelta(days=7)),
        )
        | (active_assets & Q(warranty_end__lt=today))
        | (
            active_assets
            & Q(warranty_end__range=(today, today + timedelta(days=30)))
        )
        | Q(
            lifecycle_status=LifecycleStatus.DISPOSED,
            disposal_evidence_ref="",
        )
        | (
            Q(
                lifecycle_status__in=[
                    LifecycleStatus.READY_FOR_DISPOSAL,
                    LifecycleStatus.DISPOSED,
                ],
                sanitisation_required=True,
            )
            & (~Q(sanitisation_result="Passed") | Q(sanitisation_evidence_ref=""))
        )
        | Q(lifecycle_status=LifecycleStatus.ASSIGNED, custodian_ref="")
        | Q(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__isnull=True,
        )
    )


def asset_notification_count(*, as_of: date | None = None) -> int:
    return Asset.objects.filter(asset_notification_filter(as_of=as_of)).count()


def build_asset_notifications(*, as_of: date | None = None) -> list[dict[str, Any]]:
    today = as_of or timezone.localdate()
    alerts = []
    for asset in Asset.objects.filter(asset_notification_filter(as_of=today)):
        if (
            asset.lifecycle_status == LifecycleStatus.RETURN_PENDING
            and asset.return_due_date
            and asset.return_due_date < today
        ):
            alert = {
                "severity": "critical",
                "title": "Return overdue",
                "message": f"Return was due {asset.return_due_date.isoformat()}.",
                "sort_date": asset.return_due_date,
                "priority": 0,
            }
        elif (
            asset.lifecycle_status == LifecycleStatus.RETURN_PENDING
            and asset.return_due_date
            and asset.return_due_date <= today + timedelta(days=7)
        ):
            alert = {
                "severity": "warning",
                "title": "Return due soon",
                "message": f"Return is due {asset.return_due_date.isoformat()}.",
                "sort_date": asset.return_due_date,
                "priority": 4,
            }
        elif (
            asset.lifecycle_status
            not in {LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN}
            and asset.warranty_end < today
        ):
            alert = {
                "severity": "high",
                "title": "Warranty expired",
                "message": f"Warranty expired {asset.warranty_end.isoformat()}.",
                "sort_date": asset.warranty_end,
                "priority": 1,
            }
        elif (
            asset.lifecycle_status
            not in {LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN}
            and asset.warranty_end <= today + timedelta(days=30)
        ):
            alert = {
                "severity": "notice",
                "title": "Warranty expiring",
                "message": f"Warranty ends {asset.warranty_end.isoformat()}.",
                "sort_date": asset.warranty_end,
                "priority": 5,
            }
        elif (
            asset.lifecycle_status == LifecycleStatus.DISPOSED
            and not asset.disposal_evidence_ref
        ):
            alert = {
                "severity": "high",
                "title": "Disposal evidence missing",
                "message": "Add the evidence reference for this disposed asset.",
                "sort_date": today,
                "priority": 2,
            }
        elif (
            asset.lifecycle_status
            in {LifecycleStatus.READY_FOR_DISPOSAL, LifecycleStatus.DISPOSED}
            and asset.sanitisation_required
            and (
                asset.sanitisation_result != "Passed"
                or not asset.sanitisation_evidence_ref
            )
        ):
            alert = {
                "severity": "high",
                "title": "Sanitisation evidence needs review",
                "message": "Confirm a passed result and record its evidence.",
                "sort_date": today,
                "priority": 2,
            }
        elif (
            asset.lifecycle_status == LifecycleStatus.ASSIGNED
            and not asset.custodian_ref
        ):
            alert = {
                "severity": "warning",
                "title": "Custodian reference missing",
                "message": "Confirm and record the assigned asset's custodian.",
                "sort_date": today,
                "priority": 3,
            }
        else:
            alert = {
                "severity": "warning",
                "title": "Return due date missing",
                "message": "Add a due date for this pending return.",
                "sort_date": today,
                "priority": 3,
            }
        alerts.append({"asset": asset, **alert})

    return sorted(
        alerts,
        key=lambda item: (
            item["priority"],
            item["sort_date"],
            item["asset"].asset_id,
        ),
    )


def asset_notification_context(request) -> dict[str, int]:
    user = request.user
    if not user.is_authenticated or not user.has_perm("inventory.view_asset"):
        return {"asset_notification_count": 0}
    return {"asset_notification_count": asset_notification_count()}
