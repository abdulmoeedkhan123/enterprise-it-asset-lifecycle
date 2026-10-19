from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class LifecycleStatus(models.TextChoices):
    IN_STOCK = "In Stock", "In Stock"
    ASSIGNED = "Assigned", "Assigned"
    RETURN_PENDING = "Return Pending", "Return Pending"
    IN_REPAIR = "In Repair", "In Repair"
    SANITISATION_PENDING = "Sanitisation Pending", "Sanitisation Pending"
    READY_FOR_DISPOSAL = "Ready for Disposal", "Ready for Disposal"
    DISPOSED = "Disposed", "Disposed"
    LOST_STOLEN = "Lost / Stolen", "Lost / Stolen"


class SanitisationResult(models.TextChoices):
    PASSED = "Passed", "Passed"
    FAILED = "Failed", "Failed"
    PENDING = "Pending", "Pending"


class Asset(models.Model):
    asset_id = models.CharField(max_length=32, unique=True)
    asset_type = models.CharField(max_length=32)
    manufacturer = models.CharField(max_length=64)
    model = models.CharField(max_length=96)
    serial_ref = models.CharField(max_length=64, blank=True)
    site = models.CharField(max_length=64)
    department = models.CharField(max_length=64)
    custodian_ref = models.CharField(max_length=32, blank=True)
    lifecycle_status = models.CharField(
        max_length=32,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.IN_STOCK,
        db_index=True,
    )
    purchase_date = models.DateField()
    warranty_end = models.DateField()
    return_due_date = models.DateField(null=True, blank=True, db_index=True)
    sanitisation_required = models.BooleanField(default=False)
    sanitisation_result = models.CharField(
        max_length=16, choices=SanitisationResult.choices, blank=True
    )
    sanitisation_evidence_ref = models.CharField(max_length=64, blank=True)
    disposal_evidence_ref = models.CharField(max_length=64, blank=True)
    source_last_updated = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("asset_id",)
        permissions = [
            ("transition_asset", "Can transition asset lifecycle state"),
        ]

    def __str__(self) -> str:
        return f"{self.asset_id} - {self.asset_type}"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.lifecycle_status == LifecycleStatus.ASSIGNED:
            if not self.custodian_ref.strip():
                errors["custodian_ref"] = "Assigned assets require a custodian reference."
        if self.lifecycle_status == LifecycleStatus.RETURN_PENDING and not self.return_due_date:
            errors["return_due_date"] = "Return-pending assets require a due date."
        if (
            self.lifecycle_status == LifecycleStatus.DISPOSED
            and self.sanitisation_required
            and (
                self.sanitisation_result != SanitisationResult.PASSED
                or not self.sanitisation_evidence_ref.strip()
                or not self.disposal_evidence_ref.strip()
            )
        ):
            errors["lifecycle_status"] = (
                "Disposal requires passed sanitisation and sanitisation and disposal "
                "evidence references when sanitisation is required."
            )
        if errors:
            raise ValidationError(errors)


class LifecycleEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        TRANSITIONED = "transitioned", "Transitioned"
        IMPORTED = "imported", "Imported"

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="asset_lifecycle_events",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.asset.asset_id}: {self.get_event_type_display()}"


class ImportRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    source_name = models.CharField(max_length=255)
    source_sha256 = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    rows_seen = models.PositiveIntegerField(default=0)
    rows_created = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)
    rows_unchanged = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-pk")

    def __str__(self) -> str:
        return f"{self.source_name} ({self.get_status_display()})"
