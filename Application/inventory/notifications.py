from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import Case, F, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone

from .models import Asset, LifecycleStatus


def _notification_conditions(today: date) -> dict[str, Q]:
    active_assets = ~Q(
        lifecycle_status__in=[LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN]
    )
    return {
        "return_overdue": Q(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__lt=today,
        ),
        "return_soon": Q(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__range=(today, today + timedelta(days=7)),
        ),
        "warranty_expired": active_assets & Q(warranty_end__lt=today),
        "warranty_soon": active_assets
        & Q(warranty_end__range=(today, today + timedelta(days=30))),
        "disposal_missing": Q(
            lifecycle_status=LifecycleStatus.DISPOSED,
            disposal_evidence_ref="",
        ),
        "sanitisation_missing": Q(
            lifecycle_status__in=[
                LifecycleStatus.READY_FOR_DISPOSAL,
                LifecycleStatus.DISPOSED,
            ],
            sanitisation_required=True,
        )
        & (~Q(sanitisation_result="Passed") | Q(sanitisation_evidence_ref="")),
        "custodian_missing": Q(
            lifecycle_status=LifecycleStatus.ASSIGNED,
            custodian_ref="",
        ),
        "return_due_missing": Q(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__isnull=True,
        ),
    }


def asset_notification_filter(*, as_of: date | None = None) -> Q:
    today = as_of or timezone.localdate()
    conditions = _notification_conditions(today)
    combined_filter = Q(pk__in=[])
    for condition in conditions.values():
        combined_filter |= condition
    return combined_filter


def asset_notification_queryset(*, as_of: date | None = None) -> QuerySet[Asset]:
    today = as_of or timezone.localdate()
    conditions = _notification_conditions(today)
    return (
        Asset.objects.filter(asset_notification_filter(as_of=today))
        .annotate(
            _notification_priority=Case(
                When(conditions["return_overdue"], then=Value(0)),
                When(conditions["warranty_expired"], then=Value(1)),
                When(conditions["disposal_missing"], then=Value(2)),
                When(conditions["sanitisation_missing"], then=Value(2)),
                When(conditions["custodian_missing"], then=Value(3)),
                When(conditions["return_due_missing"], then=Value(3)),
                When(conditions["return_soon"], then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            ),
            _notification_sort_date=Case(
                When(conditions["return_overdue"], then=F("return_due_date")),
                When(conditions["return_soon"], then=F("return_due_date")),
                When(conditions["warranty_expired"], then=F("warranty_end")),
                When(conditions["warranty_soon"], then=F("warranty_end")),
                default=Value(today),
            ),
        )
        .order_by("_notification_priority", "_notification_sort_date", "asset_id")
    )


def asset_notification_count(*, as_of: date | None = None) -> int:
    return Asset.objects.filter(asset_notification_filter(as_of=as_of)).count()


def build_asset_notification(
    asset: Asset, *, as_of: date | None = None
) -> dict[str, Any]:
    today = as_of or timezone.localdate()
    if (
        asset.lifecycle_status == LifecycleStatus.RETURN_PENDING
        and asset.return_due_date
        and asset.return_due_date < today
    ):
        return {
            "severity": "critical",
            "title": "Return overdue",
            "message": f"Return was due {asset.return_due_date.isoformat()}.",
            "sort_date": asset.return_due_date,
            "priority": 0,
        }
    if (
        asset.lifecycle_status
        not in {LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN}
        and asset.warranty_end < today
    ):
        return {
            "severity": "high",
            "title": "Warranty expired",
            "message": f"Warranty expired {asset.warranty_end.isoformat()}.",
            "sort_date": asset.warranty_end,
            "priority": 1,
        }
    if asset.lifecycle_status == LifecycleStatus.DISPOSED and not asset.disposal_evidence_ref:
        return {
            "severity": "high",
            "title": "Disposal evidence missing",
            "message": "Add the evidence reference for this disposed asset.",
            "sort_date": today,
            "priority": 2,
        }
    if (
        asset.lifecycle_status
        in {LifecycleStatus.READY_FOR_DISPOSAL, LifecycleStatus.DISPOSED}
        and asset.sanitisation_required
        and (
            asset.sanitisation_result != "Passed"
            or not asset.sanitisation_evidence_ref
        )
    ):
        return {
            "severity": "high",
            "title": "Sanitisation evidence needs review",
            "message": "Confirm a passed result and record its evidence.",
            "sort_date": today,
            "priority": 2,
        }
    if (
        asset.lifecycle_status == LifecycleStatus.ASSIGNED
        and not asset.custodian_ref
    ):
        return {
            "severity": "warning",
            "title": "Custodian reference missing",
            "message": "Confirm and record the assigned asset's custodian.",
            "sort_date": today,
            "priority": 3,
        }
    if (
        asset.lifecycle_status == LifecycleStatus.RETURN_PENDING
        and not asset.return_due_date
    ):
        return {
            "severity": "warning",
            "title": "Return due date missing",
            "message": "Add a due date for this pending return.",
            "sort_date": today,
            "priority": 3,
        }
    if asset.lifecycle_status == LifecycleStatus.RETURN_PENDING:
        return {
            "severity": "warning",
            "title": "Return due soon",
            "message": f"Return is due {asset.return_due_date.isoformat()}.",
            "sort_date": asset.return_due_date,
            "priority": 4,
        }
    return {
        "severity": "notice",
        "title": "Warranty expiring",
        "message": f"Warranty ends {asset.warranty_end.isoformat()}.",
        "sort_date": asset.warranty_end,
        "priority": 5,
    }


def build_asset_notifications(*, as_of: date | None = None) -> list[dict[str, Any]]:
    return [
        {"asset": asset, **build_asset_notification(asset, as_of=as_of)}
        for asset in asset_notification_queryset(as_of=as_of)
    ]


def asset_notification_context(request) -> dict[str, int]:
    user = request.user
    if not user.is_authenticated or not user.has_perm("inventory.view_asset"):
        return {"asset_notification_count": 0}
    return {"asset_notification_count": asset_notification_count()}
