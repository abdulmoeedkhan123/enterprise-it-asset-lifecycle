"""Safe, read-only natural-language query handling for the asset copilot MVP.

This first iteration deliberately uses deterministic intent matching rather than an
external LLM. It returns records only; it never changes assets or starts workflows.
An LLM can later propose a structured intent, but this module/backend must remain
the source of truth for validation and data access.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Asset, IntuneDevice, IntuneSyncRun, LifecycleStatus


MAX_QUERY_LENGTH = 500
MAX_RESULTS = 10
DEFAULT_WARRANTY_WINDOW_DAYS = 60
MAX_WARRANTY_WINDOW_DAYS = 365

STATUS_PHRASES = (
    ("ready for disposal", LifecycleStatus.READY_FOR_DISPOSAL),
    ("return pending", LifecycleStatus.RETURN_PENDING),
    ("lost / stolen", LifecycleStatus.LOST_STOLEN),
    ("lost stolen", LifecycleStatus.LOST_STOLEN),
    ("sanitisation pending", LifecycleStatus.SANITISATION_PENDING),
    ("in stock", LifecycleStatus.IN_STOCK),
    ("in repair", LifecycleStatus.IN_REPAIR),
    ("assigned", LifecycleStatus.ASSIGNED),
    ("disposed", LifecycleStatus.DISPOSED),
)


def _result(
    intent: str,
    message: str,
    queryset=None,
    *,
    metadata=None,
    intune_devices=None,
) -> dict:
    assets = list(queryset[: MAX_RESULTS + 1]) if queryset is not None else []
    total = queryset.count() if queryset is not None else 0
    truncated = total > MAX_RESULTS
    assets = assets[:MAX_RESULTS]
    devices = (
        list(intune_devices[: MAX_RESULTS + 1])
        if intune_devices is not None
        else []
    )
    device_total = intune_devices.count() if intune_devices is not None else 0
    devices_truncated = device_total > MAX_RESULTS
    devices = devices[:MAX_RESULTS]
    evidence = {
        "queried_at": timezone.now().isoformat(),
        "sources": (
            ["Local asset register", "Read-only Intune snapshot"]
            if intune_devices is not None
            else ["Local asset register"]
        ),
        "record_basis": "Stored records returned by read-only database queries.",
    }
    result_metadata = dict(metadata or {})
    result_metadata.setdefault("evidence", evidence)
    return {
        "intent": intent,
        "message": message,
        "assets": assets,
        "intune_devices": devices,
        "total": total,
        "truncated": truncated,
        "device_total": device_total,
        "devices_truncated": devices_truncated,
        "metadata": result_metadata,
        "read_only": True,
    }


def _latest_intune_snapshot():
    return (
        IntuneSyncRun.objects.filter(status=IntuneSyncRun.Status.SUCCEEDED)
        .order_by("-completed_at", "-pk")
        .first()
    )


def _intune_snapshot_result(intent: str, *, match_status=None, noncompliant=False) -> dict:
    latest = _latest_intune_snapshot()
    if latest is None:
        return _result(
            intent,
            "No successful Intune snapshot is available. No live Intune query was run.",
            intune_devices=IntuneDevice.objects.none(),
            metadata={
                "snapshot_available": False,
                "evidence": {
                    "queried_at": timezone.now().isoformat(),
                    "sources": ["Intune sync history"],
                    "record_basis": "No successful snapshot exists in the local database.",
                },
            },
        )
    devices = IntuneDevice.objects.filter(last_seen_run=latest).select_related(
        "matched_asset", "last_seen_run"
    )
    if match_status:
        devices = devices.filter(match_status=match_status)
    if noncompliant:
        devices = devices.filter(
            Q(compliance_state__iexact="noncompliant")
            | Q(compliance_state__iexact="non-compliant")
            | Q(compliance_state__iexact="notcompliant")
            | Q(compliance_state__iexact="not compliant")
        )
    if intent == "intune_snapshot_status":
        return _result(
            intent,
            "Showing the latest successful Intune snapshot metadata; this is not a live Graph query.",
            intune_devices=IntuneDevice.objects.none(),
            metadata={
                "snapshot_available": True,
                "snapshot_completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
                "snapshot_records_received": latest.records_received,
                "snapshot_run_id": latest.pk,
                "snapshot_status": latest.get_status_display(),
                "evidence": {
                    "queried_at": timezone.now().isoformat(),
                    "sources": ["Intune sync history"],
                    "record_basis": "Latest successful local snapshot run.",
                    "snapshot_completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
                },
            },
        )
    return _result(
        intent,
        "Results are limited to devices present in the latest successful Intune snapshot. Compliance and matching values are observations, not an approval to act.",
        intune_devices=devices.order_by("device_name", "managed_device_id"),
        metadata={
            "snapshot_available": True,
            "snapshot_completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
            "snapshot_records_received": latest.records_received,
            "snapshot_run_id": latest.pk,
            "evidence": {
                "queried_at": timezone.now().isoformat(),
                "sources": ["Read-only Intune snapshot", "Local asset register for exact-serial match references"],
                "record_basis": "Only records whose last_seen_run is the latest successful sync are included.",
                "snapshot_completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
            },
        },
    )


def run_copilot_query(query: str, *, today=None) -> dict:
    """Interpret a supported question and return authorised-to-view asset rows.

    Callers must enforce authentication and inventory.view_asset before using this
    function. Queries are never interpolated into SQL and no mutations are performed.
    """
    raw_query = (query or "").strip()
    if not raw_query:
        return {
            "intent": "empty",
            "message": "Ask a question about asset inventory, overdue returns, or warranties.",
            "assets": [],
            "total": 0,
            "truncated": False,
            "metadata": {},
            "read_only": True,
        }
    if len(raw_query) > MAX_QUERY_LENGTH:
        return {
            "intent": "invalid",
            "message": f"Please keep your question to {MAX_QUERY_LENGTH} characters or fewer.",
            "assets": [],
            "total": 0,
            "truncated": False,
            "metadata": {},
            "read_only": True,
        }

    normalized = " ".join(raw_query.casefold().split())
    today = today or timezone.localdate()
    assets = Asset.objects.all()

    if "intune" in normalized:
        if any(term in normalized for term in ("last successful", "snapshot status", "freshness", "last sync", "latest sync")):
            return _intune_snapshot_result("intune_snapshot_status")
        if any(term in normalized for term in ("non-compliant", "non compliant", "noncompliant", "not compliant")):
            return _intune_snapshot_result("intune_noncompliant")
        if "duplicate" in normalized or "ambiguous" in normalized:
            return _intune_snapshot_result(
                "intune_match_review", match_status=IntuneDevice.MatchStatus.DUPLICATE
            )
        if "unmatched" in normalized or "no match" in normalized or "not matched" in normalized:
            return _intune_snapshot_result(
                "intune_match_review", match_status=IntuneDevice.MatchStatus.UNMATCHED
            )
        if any(term in normalized for term in ("device", "devices", "inventory", "list", "show", "find")):
            return _intune_snapshot_result("intune_devices")
        return {
            "intent": "unsupported",
            "message": "For Intune, ask for devices in the latest snapshot, non-compliant devices, unmatched/duplicate matches, or the latest successful snapshot time.",
            "assets": [],
            "intune_devices": [],
            "total": 0,
            "truncated": False,
            "device_total": 0,
            "devices_truncated": False,
            "metadata": {},
            "read_only": True,
        }

    if "overdue" in normalized and ("return" in normalized or "asset" in normalized):
        queryset = assets.filter(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__lt=today,
        ).order_by("return_due_date", "asset_id")
        return _result(
            "overdue_returns",
            "Overdue return records found. Review each record before taking action.",
            queryset,
        )

    if "warrant" in normalized and any(word in normalized for word in ("expir", "due", "next", "soon", "ending")):
        match = re.search(r"\b(\d{1,3})\s+days?\b", normalized)
        days = int(match.group(1)) if match else DEFAULT_WARRANTY_WINDOW_DAYS
        days = max(1, min(days, MAX_WARRANTY_WINDOW_DAYS))
        end_date = today + timedelta(days=days)
        queryset = assets.exclude(
            lifecycle_status__in=(LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN)
        ).filter(warranty_end__range=(today, end_date)).order_by("warranty_end", "asset_id")
        return _result(
            "warranty_expiry",
            f"Active-asset warranties expiring in the next {days} days (inclusive of today).",
            queryset,
            metadata={"days": days, "from_date": today.isoformat(), "to_date": end_date.isoformat()},
        )

    for phrase, status in STATUS_PHRASES:
        if phrase in normalized and any(word in normalized for word in ("asset", "assets", "show", "find", "list", "which", "all")):
            queryset = assets.filter(lifecycle_status=status).order_by("asset_id")
            return _result(
                "lifecycle_status",
                f"Assets currently recorded as '{status}'. This is based on the stored lifecycle status.",
                queryset,
                metadata={"status": status},
            )

    # Search for an exact asset identifier or serial/custodian reference.
    identifier = re.search(r"\b(?:asset\s+)?([A-Za-z]{2,8}[-_][A-Za-z0-9_-]{2,})\b", raw_query)
    if identifier:
        term = identifier.group(1)
        queryset = assets.filter(
            Q(asset_id__iexact=term)
            | Q(serial_ref__iexact=term)
            | Q(custodian_ref__iexact=term)
        ).order_by("asset_id")
        return _result(
            "asset_lookup",
            f"Lookup results for '{term}'.",
            queryset,
            metadata={"term": term},
        )

    return {
        "intent": "unsupported",
        "message": (
            "I can currently find an asset by asset ID/serial/custodian reference, "
            "list overdue returns, show warranties expiring within a number of days, "
            "or filter by lifecycle status. I have not changed any records."
        ),
        "assets": [],
        "total": 0,
        "truncated": False,
        "metadata": {},
        "read_only": True,
    }


def run_copilot_intent(intent_document: dict, *, today: date | None = None) -> dict:
    """Execute only a validated, read-only intent through Django ORM queries."""
    from .copilot_llm import validate_asset_intent

    intent = validate_asset_intent(intent_document)
    if intent is None:
        raise ValueError("Copilot intent is empty.")
    today = today or timezone.localdate()
    assets = Asset.objects.all()
    intent_name = intent["intent"]
    if intent_name == "intune_snapshot_status":
        return _intune_snapshot_result(intent_name)
    if intent_name == "intune_devices":
        return _intune_snapshot_result(intent_name)
    if intent_name == "intune_noncompliant":
        return _intune_snapshot_result(intent_name, noncompliant=True)
    if intent_name == "intune_match_review":
        return _intune_snapshot_result(intent_name, match_status=intent["status"])
    if intent_name == "overdue_returns":
        return _result(
            "overdue_returns",
            "Overdue return records found. Review each record before taking action.",
            assets.filter(
                lifecycle_status=LifecycleStatus.RETURN_PENDING,
                return_due_date__lt=today,
            ).order_by("return_due_date", "asset_id"),
        )
    if intent_name == "warranty_expiry":
        days = intent["days"]
        end_date = today + timedelta(days=days)
        return _result(
            "warranty_expiry",
            f"Active-asset warranties expiring in the next {days} days (inclusive of today).",
            assets.exclude(
                lifecycle_status__in=(
                    LifecycleStatus.DISPOSED,
                    LifecycleStatus.LOST_STOLEN,
                )
            )
            .filter(warranty_end__range=(today, end_date))
            .order_by("warranty_end", "asset_id"),
            metadata={
                "days": days,
                "from_date": today.isoformat(),
                "to_date": end_date.isoformat(),
            },
        )
    if intent_name == "lifecycle_status":
        status = intent["status"]
        return _result(
            "lifecycle_status",
            f"Assets currently recorded as '{status}'. This is based on stored lifecycle status.",
            assets.filter(lifecycle_status=status).order_by("asset_id"),
            metadata={"status": status},
        )
    if intent_name == "asset_search":
        term = intent["term"]
        field = intent["field"]
        searchable_fields = {
            "asset_id",
            "asset_type",
            "manufacturer",
            "model",
            "serial_ref",
            "site",
            "department",
            "custodian_ref",
        }
        if field == "any":
            filters = Q()
            for searchable_field in searchable_fields:
                filters |= Q(**{f"{searchable_field}__icontains": term})
            queryset = assets.filter(filters)
        elif field in searchable_fields:
            queryset = assets.filter(**{f"{field}__icontains": term})
        else:
            raise ValueError("Copilot intent contains an unsupported search field.")
        return _result(
            "asset_search",
            f"Asset search results for '{term}'.",
            queryset.order_by("asset_id"),
            metadata={"term": term, "field": field},
        )
    raise ValueError("Copilot intent is not supported.")
