from __future__ import annotations

from datetime import date
from typing import Any

from django.db.models import Count, Q, QuerySet, Subquery

from .models import Asset, LifecycleStatus


def build_asset_quality_report(
    assets: QuerySet[Asset], *, as_of: date
) -> dict[str, Any]:
    duplicate_serials = (
        assets.exclude(serial_ref="")
        .values("serial_ref")
        .annotate(record_count=Count("pk"))
        .filter(record_count__gt=1)
        .values("serial_ref")
    )
    duplicate_serial_filter = Q(serial_ref__in=Subquery(duplicate_serials))
    checks = (
        (
            "assigned_without_custodian",
            "Assigned assets missing custodian reference",
            Q(lifecycle_status=LifecycleStatus.ASSIGNED, custodian_ref=""),
        ),
        (
            "return_pending_without_due_date",
            "Return-pending assets missing due date",
            Q(
                lifecycle_status=LifecycleStatus.RETURN_PENDING,
                return_due_date__isnull=True,
            ),
        ),
        (
            "disposition_missing_sanitisation_evidence",
            "Disposition records missing passed sanitisation evidence",
            Q(
                lifecycle_status__in=[
                    LifecycleStatus.READY_FOR_DISPOSAL,
                    LifecycleStatus.DISPOSED,
                ],
                sanitisation_required=True,
            )
            & (
                ~Q(sanitisation_result="Passed")
                | Q(sanitisation_evidence_ref="")
            ),
        ),
        (
            "disposed_without_evidence",
            "Disposed assets missing disposal evidence",
            Q(
                lifecycle_status=LifecycleStatus.DISPOSED,
                disposal_evidence_ref="",
            ),
        ),
        (
            "stale_source_records",
            "Source records not updated in the last 90 days",
            Q(source_last_updated__lt=as_of.fromordinal(as_of.toordinal() - 90)),
        ),
        (
            "warranty_before_purchase",
            "Warranty end date before purchase date",
            Q(warranty_end__lt=models.F("purchase_date")),
        ),
        (
            "duplicate_serial_assets",
            "Assets in duplicate serial-reference groups",
            duplicate_serial_filter,
        ),
    )
    checks_report = []
    issue_filter = Q(pk__in=[])
    for code, label, condition in checks:
        checks_report.append(
            {"code": code, "label": label, "count": assets.filter(condition).count()}
        )
        issue_filter |= condition

    return {
        "asset_count": assets.count(),
        "assets_with_issues": assets.filter(issue_filter).distinct().count(),
        "checks": checks_report,
    }


def profile_asset_rows(rows: list[dict[str, str]], *, as_of: date) -> dict[str, int]:
    serial_counts: dict[str, int] = {}
    counts = {
        "records_profiled": len(rows),
        "assigned_without_custodian": 0,
        "return_pending_without_due_date": 0,
        "disposition_missing_sanitisation_evidence": 0,
        "disposed_without_evidence": 0,
        "stale_source_records": 0,
        "warranty_before_purchase": 0,
        "duplicate_serial_assets": 0,
    }
    stale_cutoff = date.fromordinal(as_of.toordinal() - 90)
    for row in rows:
        status = row["lifecycle_status"]
        serial_ref = row["serial_ref"].strip()
        if serial_ref:
            serial_counts[serial_ref] = serial_counts.get(serial_ref, 0) + 1
        if status == LifecycleStatus.ASSIGNED and not row["custodian_ref"].strip():
            counts["assigned_without_custodian"] += 1
        if status == LifecycleStatus.RETURN_PENDING and not row["return_due_date"]:
            counts["return_pending_without_due_date"] += 1
        if (
            status in {LifecycleStatus.READY_FOR_DISPOSAL, LifecycleStatus.DISPOSED}
            and row["sanitisation_required"] == "true"
            and (
                row["sanitisation_result"] != "Passed"
                or not row["sanitisation_evidence_ref"].strip()
            )
        ):
            counts["disposition_missing_sanitisation_evidence"] += 1
        if status == LifecycleStatus.DISPOSED and not row["disposal_evidence_ref"].strip():
            counts["disposed_without_evidence"] += 1
        try:
            if date.fromisoformat(row["last_updated"]) < stale_cutoff:
                counts["stale_source_records"] += 1
            if date.fromisoformat(row["warranty_end"]) < date.fromisoformat(
                row["purchase_date"]
            ):
                counts["warranty_before_purchase"] += 1
        except ValueError:
            continue
    counts["duplicate_serial_assets"] = sum(
        count for count in serial_counts.values() if count > 1
    )
    return counts
