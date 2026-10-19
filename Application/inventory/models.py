from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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
    serial_ref = models.CharField(max_length=64, blank=True, db_index=True)
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
    procurement_request = models.ForeignKey(
        "ProcurementRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_assets",
    )
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
            self.lifecycle_status
            in {LifecycleStatus.READY_FOR_DISPOSAL, LifecycleStatus.DISPOSED}
            and self.sanitisation_required
            and (
                self.sanitisation_result != SanitisationResult.PASSED
                or not self.sanitisation_evidence_ref.strip()
                or (
                    self.lifecycle_status == LifecycleStatus.DISPOSED
                    and not self.disposal_evidence_ref.strip()
                )
            )
        ):
            errors["lifecycle_status"] = "Disposition requires passed sanitisation and its evidence."
        if (
            self.lifecycle_status == LifecycleStatus.DISPOSED
            and not self.disposal_evidence_ref.strip()
        ):
            errors["disposal_evidence_ref"] = "Disposed assets require a disposal evidence reference."
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

    source_name = models.CharField(max_length=255)
    source_sha256 = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    rows_seen = models.PositiveIntegerField(default=0)
    rows_created = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)
    rows_unchanged = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    quality_summary = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-pk")

    def __str__(self) -> str:
        return f"{self.source_name} ({self.get_status_display()})"


class IdentityLink(models.Model):
    """Explicit mapping between a SCIM subject identifier and local custodian ref."""

    provider = models.CharField(max_length=32, default="scim")
    external_subject_id = models.CharField(max_length=255)
    custodian_ref = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "external_subject_id"),
                name="unique_provider_external_subject",
            ),
            models.UniqueConstraint(
                fields=("provider", "custodian_ref"),
                name="unique_provider_custodian_ref",
            ),
        ]
        ordering = ("provider", "custodian_ref")

    def __str__(self) -> str:
        return f"{self.provider}: {self.custodian_ref}"


class ReturnWorkItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"
        DISMISSED = "dismissed", "Dismissed"

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="return_work_items")
    source_provider = models.CharField(max_length=32, default="scim")
    source_event_id = models.CharField(max_length=255, unique=True)
    custodian_ref = models.CharField(max_length=32)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    resolution_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("status", "-created_at")

    def __str__(self) -> str:
        return f"{self.asset.asset_id}: return review ({self.status})"

    def save(self, *args, **kwargs):
        if self.status in {self.Status.CLOSED, self.Status.DISMISSED}:
            self.closed_at = self.closed_at or timezone.now()
        else:
            self.closed_at = None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"closed_at"}
        super().save(*args, **kwargs)


class IntegrationRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    provider = models.CharField(max_length=32, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    records_received = models.PositiveIntegerField(default=0)
    identities_matched = models.PositiveIntegerField(default=0)
    work_items_created = models.PositiveIntegerField(default=0)
    work_items_existing = models.PositiveIntegerField(default=0)
    identities_unmatched = models.PositiveIntegerField(default=0)
    error_summary = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at", "-pk")

    def __str__(self) -> str:
        return f"{self.provider} integration ({self.get_status_display()})"


class MaintenanceWorkOrder(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_PARTS = "waiting_parts", "Waiting for parts"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, related_name="maintenance_orders"
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    priority = models.CharField(
        max_length=8, choices=Priority.choices, default=Priority.NORMAL, db_index=True
    )
    vendor = models.CharField(max_length=128, blank=True)
    target_date = models.DateField(null=True, blank=True, db_index=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_maintenance_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("status", "-priority", "target_date", "-created_at")

    def __str__(self) -> str:
        return f"{self.asset.asset_id}: {self.title}"

    def save(self, *args, **kwargs):
        self.completed_at = (
            self.completed_at or timezone.now()
            if self.status == self.Status.COMPLETED
            else None
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"completed_at"}
        super().save(*args, **kwargs)


class MaintenanceWorkOrderEvent(models.Model):
    work_order = models.ForeignKey(
        MaintenanceWorkOrder,
        on_delete=models.PROTECT,
        related_name="events",
    )
    from_status = models.CharField(
        max_length=16, choices=MaintenanceWorkOrder.Status.choices, blank=True
    )
    to_status = models.CharField(
        max_length=16, choices=MaintenanceWorkOrder.Status.choices
    )
    note = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_work_order_events",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.work_order}: {self.get_to_status_display()}"


class ProcurementRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ORDERED = "ordered", "Ordered"
        PARTIALLY_RECEIVED = "partially_received", "Partially received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    class DeliveryStatus(models.TextChoices):
        NOT_ORDERED = "not_ordered", "Not ordered"
        ORDERED = "ordered", "Ordered"
        IN_TRANSIT = "in_transit", "In transit"
        DELAYED = "delayed", "Delayed"
        PARTIALLY_RECEIVED = "partially_received", "Partially received"
        RECEIVED = "received", "Received"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procurement_requests",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    justification = models.TextField()
    quantity = models.PositiveSmallIntegerField()
    required_by = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    selected_quote = models.ForeignKey(
        "ProcurementQuote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="selected_for_requests",
    )
    purchase_order_reference = models.CharField(max_length=64, blank=True)
    delivery_status = models.CharField(
        max_length=24,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.NOT_ORDERED,
        db_index=True,
    )
    expected_delivery_date = models.DateField(null=True, blank=True)
    tracking_reference = models.CharField(max_length=64, blank=True)
    quantity_received = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        permissions = [
            ("approve_procurementrequest", "Can approve procurement requests"),
            ("manage_procurementrequest", "Can place and receive procurement orders"),
            ("view_all_procurementrequests", "Can view all procurement requests"),
        ]

    def __str__(self) -> str:
        return f"PR-{self.pk or 'new'}: {self.title}"


class ProcurementQuote(models.Model):
    request = models.ForeignKey(
        ProcurementRequest, on_delete=models.CASCADE, related_name="quotes"
    )
    supplier = models.CharField(max_length=128)
    quote_reference = models.CharField(max_length=64, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_days = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("unit_cost", "supplier")
        constraints = [
            models.UniqueConstraint(
                fields=("request", "supplier", "quote_reference"),
                name="unique_procurement_supplier_quote",
            )
        ]

    def __str__(self) -> str:
        return f"{self.supplier}: {self.unit_cost}"


class ProcurementReceipt(models.Model):
    request = models.ForeignKey(
        ProcurementRequest, on_delete=models.PROTECT, related_name="receipts"
    )
    receipt_reference = models.CharField(max_length=64)
    quantity = models.PositiveSmallIntegerField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="procurement_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("request", "receipt_reference"),
                name="unique_procurement_receipt_reference",
            )
        ]

    def __str__(self) -> str:
        return f"{self.request}: {self.receipt_reference} ({self.quantity})"


class ProcurementEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Request created"
        QUOTE_ADDED = "quote_added", "Quote added"
        QUOTE_SELECTED = "quote_selected", "Quote selected"
        SUBMITTED = "submitted", "Submitted for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ORDERED = "ordered", "Purchase order placed"
        DELIVERY_UPDATED = "delivery_updated", "Delivery status updated"
        RECEIVED = "received", "Goods received"
        ASSET_REGISTERED = "asset_registered", "Asset registered"
        CANCELLED = "cancelled", "Cancelled"

    request = models.ForeignKey(
        ProcurementRequest, on_delete=models.PROTECT, related_name="events"
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="procurement_events",
    )
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.request}: {self.get_event_type_display()}"


class DisposalCase(models.Model):
    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"

    class Method(models.TextChoices):
        RECYCLE = "recycle", "Recycle"
        SECURE_DESTRUCTION = "secure_destruction", "Secure destruction"
        RESALE = "resale", "Resale"
        DONATION = "donation", "Donation"
        RETURN_TO_VENDOR = "return_to_vendor", "Return to vendor"
        OTHER = "other", "Other"

    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, related_name="disposal_cases"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_disposal_cases",
    )
    reason = models.TextField()
    method = models.CharField(max_length=24, choices=Method.choices)
    sanitisation_result = models.CharField(
        max_length=16, choices=SanitisationResult.choices, blank=True
    )
    sanitisation_evidence_ref = models.CharField(max_length=64, blank=True)
    disposal_evidence_ref = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING_APPROVAL,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("status", "-created_at")
        permissions = [
            ("approve_disposalcase", "Can approve disposal requests"),
            ("complete_disposalcase", "Can complete approved disposals"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("asset",),
                condition=models.Q(
                    status__in=["pending_approval", "approved"]
                ),
                name="unique_active_disposal_case_per_asset",
            )
        ]

    def __str__(self) -> str:
        return f"{self.asset.asset_id}: disposal ({self.get_status_display()})"

    def clean(self) -> None:
        if self.asset_id and self.asset.lifecycle_status != LifecycleStatus.READY_FOR_DISPOSAL:
            raise ValidationError(
                {"asset": "Asset must be Ready for Disposal before a disposal request."}
            )
        if self.asset_id and self.asset.sanitisation_required:
            if self.sanitisation_result != SanitisationResult.PASSED:
                raise ValidationError(
                    {"sanitisation_result": "Passed sanitisation is required."}
                )
            if not self.sanitisation_evidence_ref.strip():
                raise ValidationError(
                    {"sanitisation_evidence_ref": "Sanitisation evidence is required."}
                )


class DisposalEvent(models.Model):
    class EventType(models.TextChoices):
        REQUESTED = "requested", "Disposal requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Disposal completed"

    case = models.ForeignKey(
        DisposalCase, on_delete=models.PROTECT, related_name="events"
    )
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="disposal_events",
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.case}: {self.get_event_type_display()}"


class SoftwareProduct(models.Model):
    class Category(models.TextChoices):
        APPLICATION = "application", "Application"
        OPERATING_SYSTEM = "operating_system", "Operating system"
        SAAS = "saas", "SaaS"
        SECURITY = "security", "Security"
        OTHER = "other", "Other"

    name = models.CharField(max_length=128)
    publisher = models.CharField(max_length=128)
    version = models.CharField(max_length=64, blank=True)
    category = models.CharField(
        max_length=24, choices=Category.choices, default=Category.APPLICATION
    )
    description = models.TextField(blank=True)
    end_of_support = models.DateField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "publisher", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("name", "publisher", "version"),
                name="unique_software_product_version",
            )
        ]

    def __str__(self) -> str:
        version = f" {self.version}" if self.version else ""
        return f"{self.name}{version} ({self.publisher})"


class SoftwareContract(models.Model):
    class ContractType(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        PERPETUAL = "perpetual", "Perpetual licence"
        MAINTENANCE = "maintenance", "Maintenance"
        OTHER = "other", "Other"

    class LicenseMetric(models.TextChoices):
        NAMED_USER = "named_user", "Named user"
        DEVICE = "device", "Device"
        CONCURRENT = "concurrent", "Concurrent use"
        SITE = "site", "Site"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RENEWED = "renewed", "Renewed"
        CANCELLED = "cancelled", "Cancelled"

    product = models.ForeignKey(
        SoftwareProduct, on_delete=models.PROTECT, related_name="contracts"
    )
    supplier = models.CharField(max_length=128)
    contract_reference = models.CharField(max_length=64, blank=True)
    contract_type = models.CharField(
        max_length=16, choices=ContractType.choices, default=ContractType.SUBSCRIPTION
    )
    license_metric = models.CharField(
        max_length=16, choices=LicenseMetric.choices, default=LicenseMetric.NAMED_USER
    )
    purchased_quantity = models.PositiveIntegerField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    renewal_notice_days = models.PositiveSmallIntegerField(default=90)
    auto_renew = models.BooleanField(default=False)
    annual_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")
    document_reference = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    renewal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="renewals",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_software_contracts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("end_date", "product__name", "-created_at")
        permissions = [
            ("view_all_softwarecontracts", "Can view all software contracts"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(purchased_quantity__gte=1),
                name="software_contract_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(renewal_notice_days__lte=365),
                name="software_contract_notice_max_365",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product}: {self.get_contract_type_display()} ({self.supplier})"

    @property
    def assigned_quantity(self) -> int:
        return sum(
            assignment.status == SoftwareLicenseAssignment.Status.ACTIVE
            for assignment in self.assignments.all()
        )

    @property
    def available_quantity(self) -> int:
        return max(self.purchased_quantity - self.assigned_quantity, 0)

    @property
    def is_expired(self) -> bool:
        return bool(
            self.end_date
            and self.end_date < timezone.localdate()
            and self.status == self.Status.ACTIVE
        )

    @property
    def renewal_due(self) -> bool:
        today = timezone.localdate()
        return bool(
            self.status == self.Status.ACTIVE
            and self.end_date
            and self.end_date <= today + timedelta(days=self.renewal_notice_days)
        )

    def clean(self) -> None:
        errors = {}
        if self.annual_cost is not None and self.annual_cost < 0:
            errors["annual_cost"] = "Annual cost cannot be negative."
        if self.currency and len(self.currency) != 3:
            errors["currency"] = "Enter a three-letter currency code."
        if self.start_date and self.end_date and self.start_date > self.end_date:
            errors["end_date"] = "Contract end date must be on or after its start date."
        if (
            self.contract_type == self.ContractType.SUBSCRIPTION
            and not self.end_date
        ):
            errors["end_date"] = "Subscription contracts need an end or renewal date."
        if self.renewal_of_id and self.product_id and self.renewal_of.product_id != self.product_id:
            errors["renewal_of"] = "A renewal must belong to the same software product."
        if errors:
            raise ValidationError(errors)


class SoftwareLicenseAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Assigned"
        RELEASED = "released", "Released"

    contract = models.ForeignKey(
        SoftwareContract, on_delete=models.PROTECT, related_name="assignments"
    )
    assignee_ref = models.CharField(max_length=64)
    department = models.CharField(max_length=64, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="software_license_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="released_software_license_assignments",
    )
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("status", "assignee_ref")
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "assignee_ref"),
                condition=models.Q(status="active"),
                name="unique_active_software_license_assignment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.contract.product}: {self.assignee_ref} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.status == self.Status.RELEASED:
            self.released_at = self.released_at or timezone.now()
        else:
            self.released_at = None
            self.released_by = None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"released_at", "released_by"}
        super().save(*args, **kwargs)
