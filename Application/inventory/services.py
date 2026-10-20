from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    Asset,
    DisposalCase,
    DisposalEvent,
    LifecycleEvent,
    LifecycleStatus,
    ReturnWorkItem,
    ReturnWorkItemEvent,
    SanitisationResult,
)


ALLOWED_TRANSITIONS = {
    LifecycleStatus.IN_STOCK: {
        LifecycleStatus.ASSIGNED,
        LifecycleStatus.IN_REPAIR,
        LifecycleStatus.READY_FOR_DISPOSAL,
        LifecycleStatus.LOST_STOLEN,
    },
    LifecycleStatus.ASSIGNED: {
        LifecycleStatus.RETURN_PENDING,
        LifecycleStatus.LOST_STOLEN,
    },
    LifecycleStatus.RETURN_PENDING: {
        LifecycleStatus.IN_STOCK,
        LifecycleStatus.IN_REPAIR,
        LifecycleStatus.READY_FOR_DISPOSAL,
        LifecycleStatus.LOST_STOLEN,
    },
    LifecycleStatus.IN_REPAIR: {
        LifecycleStatus.IN_STOCK,
        LifecycleStatus.READY_FOR_DISPOSAL,
        LifecycleStatus.LOST_STOLEN,
    },
    LifecycleStatus.SANITISATION_PENDING: {
        LifecycleStatus.READY_FOR_DISPOSAL,
        LifecycleStatus.IN_REPAIR,
    },
    LifecycleStatus.READY_FOR_DISPOSAL: set(),
    LifecycleStatus.DISPOSED: set(),
    LifecycleStatus.LOST_STOLEN: {
        LifecycleStatus.RETURN_PENDING,
    },
}


@transaction.atomic
def transition_asset(
    *,
    asset_id: int,
    to_status: str,
    actor,
    reason: str,
    return_due_date=None,
    sanitisation_result: str = "",
    sanitisation_evidence_ref: str = "",
    disposal_evidence_ref: str = "",
    approved_disposal_case_id: int | None = None,
) -> Asset:
    """Apply an allowed status transition and write its audit event atomically."""
    asset = Asset.objects.select_for_update().get(pk=asset_id)
    allowed = ALLOWED_TRANSITIONS.get(asset.lifecycle_status, set())
    if to_status == LifecycleStatus.DISPOSED:
        if (
            asset.lifecycle_status != LifecycleStatus.READY_FOR_DISPOSAL
            or approved_disposal_case_id is None
        ):
            raise ValidationError(
                "Disposal requires a separately approved disposal case."
            )
        try:
            disposal_case = DisposalCase.objects.select_for_update().get(
                pk=approved_disposal_case_id,
                asset=asset,
                status=DisposalCase.Status.APPROVED,
            )
        except DisposalCase.DoesNotExist as error:
            raise ValidationError(
                "Disposal requires a separately approved disposal case."
            ) from error
        if not disposal_case.events.filter(
            event_type=DisposalEvent.EventType.APPROVED
        ).exclude(actor=actor).exists():
            raise ValidationError(
                "The disposal approver cannot also complete the disposal."
            )
    elif to_status not in allowed:
        raise ValidationError(
            f"Transition from {asset.lifecycle_status} to {to_status} is not allowed."
        )
    if to_status == LifecycleStatus.RETURN_PENDING and not return_due_date:
        raise ValidationError("A return due date is required for Return Pending.")

    old_status = asset.lifecycle_status
    asset.lifecycle_status = to_status
    if return_due_date is not None:
        asset.return_due_date = return_due_date
    if sanitisation_result:
        asset.sanitisation_result = sanitisation_result
    if sanitisation_evidence_ref:
        asset.sanitisation_evidence_ref = sanitisation_evidence_ref
    if disposal_evidence_ref:
        asset.disposal_evidence_ref = disposal_evidence_ref
    asset.full_clean()
    asset.save()
    LifecycleEvent.objects.create(
        asset=asset,
        event_type=LifecycleEvent.EventType.TRANSITIONED,
        from_status=old_status,
        to_status=to_status,
        reason=reason,
        actor=actor,
    )
    return asset


@transaction.atomic
def transition_return_work_item(
    *,
    work_item_id: int,
    to_status: str,
    actor,
    note: str,
) -> ReturnWorkItem:
    work_item = ReturnWorkItem.objects.select_for_update().get(pk=work_item_id)
    allowed = {
        ReturnWorkItem.Status.OPEN: {ReturnWorkItem.Status.IN_PROGRESS},
        ReturnWorkItem.Status.IN_PROGRESS: {
            ReturnWorkItem.Status.OPEN,
            ReturnWorkItem.Status.CLOSED,
            ReturnWorkItem.Status.DISMISSED,
        },
        ReturnWorkItem.Status.CLOSED: {ReturnWorkItem.Status.OPEN},
        ReturnWorkItem.Status.DISMISSED: {ReturnWorkItem.Status.OPEN},
    }
    if to_status not in allowed.get(work_item.status, set()):
        raise ValidationError(
            f"Transition from {work_item.status} to {to_status} is not allowed."
        )

    old_status = work_item.status
    work_item.status = to_status
    work_item.resolution_note = (
        note
        if to_status in {ReturnWorkItem.Status.CLOSED, ReturnWorkItem.Status.DISMISSED}
        else ""
    )
    work_item.save(update_fields=("status", "resolution_note", "updated_at"))
    ReturnWorkItemEvent.objects.create(
        work_item=work_item,
        from_status=old_status,
        to_status=to_status,
        note=note,
        actor=actor,
    )
    return work_item
