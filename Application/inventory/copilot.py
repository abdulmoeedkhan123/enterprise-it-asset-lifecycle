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

from .models import Asset, LifecycleStatus


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


def _result(intent: str, message: str, queryset=None, *, metadata=None) -> dict:
    assets = list(queryset[: MAX_RESULTS + 1]) if queryset is not None else []
    total = len(assets)
    truncated = total > MAX_RESULTS
    assets = assets[:MAX_RESULTS]
    return {
        "intent": intent,
        "message": message,
        "assets": assets,
        "total": total if not truncated else f"at least {MAX_RESULTS + 1}",
        "truncated": truncated,
        "metadata": metadata or {},
        "read_only": True,
    }


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
