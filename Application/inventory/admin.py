from django.contrib import admin
from django.db import transaction

from .models import (
    Asset,
    DisposalCase,
    DisposalEvent,
    IdentityLink,
    ImportRun,
    IntegrationRun,
    IntuneDevice,
    IntuneSyncRun,
    LifecycleEvent,
    MaintenanceWorkOrder,
    MaintenanceWorkOrderEvent,
    ProcurementEvent,
    ProcurementQuote,
    ProcurementReceipt,
    ProcurementRequest,
    ReturnWorkItem,
    ReturnWorkItemEvent,
    SoftwareContract,
    SoftwareLicenseAssignment,
    SoftwareProduct,
)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "asset_id",
        "asset_type",
        "site",
        "department",
        "lifecycle_status",
        "custodian_ref",
        "warranty_end",
    )
    list_filter = ("site", "lifecycle_status", "asset_type", "department")
    search_fields = ("asset_id", "serial_ref", "custodian_ref")
    readonly_fields = (
        "created_at",
        "updated_at",
        "lifecycle_status",
        "procurement_request",
    )
    ordering = ("asset_id",)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        previous_status = None
        changed_fields = []
        if change:
            previous = Asset.objects.get(pk=obj.pk)
            previous_status = previous.lifecycle_status
            changed_fields = [
                field
                for field in form.changed_data
                if field != "lifecycle_status"
            ]
        super().save_model(request, obj, form, change)
        if change and changed_fields:
            LifecycleEvent.objects.create(
                asset=obj,
                event_type=LifecycleEvent.EventType.UPDATED,
                from_status=previous_status or obj.lifecycle_status,
                to_status=obj.lifecycle_status,
                reason="Asset details updated through administration",
                details={"changed_fields": changed_fields},
                actor=request.user,
            )
        elif not change:
            LifecycleEvent.objects.create(
                asset=obj,
                event_type=LifecycleEvent.EventType.CREATED,
                to_status=obj.lifecycle_status,
                reason="Asset record created through administration",
                actor=request.user,
            )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LifecycleEvent)
class LifecycleEventAdmin(admin.ModelAdmin):
    list_display = ("asset", "event_type", "from_status", "to_status", "actor", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("asset__asset_id", "reason")
    readonly_fields = tuple(field.name for field in LifecycleEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = (
        "source_name",
        "status",
        "rows_seen",
        "rows_created",
        "rows_updated",
        "rows_rejected",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "started_at")
    search_fields = ("source_name", "source_sha256")
    readonly_fields = tuple(field.name for field in ImportRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdentityLink)
class IdentityLinkAdmin(admin.ModelAdmin):
    list_display = ("provider", "external_subject_id", "custodian_ref", "created_at")
    list_filter = ("provider",)
    search_fields = ("external_subject_id", "custodian_ref")
    readonly_fields = ("created_at",)


@admin.register(ReturnWorkItem)
class ReturnWorkItemAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "custodian_ref",
        "source_provider",
        "status",
        "created_at",
        "closed_at",
    )
    list_filter = ("status", "source_provider", "created_at")
    search_fields = ("asset__asset_id", "custodian_ref")
    readonly_fields = (
        "asset",
        "source_provider",
        "source_event_id",
        "custodian_ref",
        "status",
        "resolution_note",
        "created_at",
        "updated_at",
        "closed_at",
    )
    fields = (
        "asset",
        "source_provider",
        "source_event_id",
        "custodian_ref",
        "status",
        "resolution_note",
        "created_at",
        "updated_at",
        "closed_at",
    )
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReturnWorkItemEvent)
class ReturnWorkItemEventAdmin(admin.ModelAdmin):
    list_display = ("work_item", "from_status", "to_status", "actor", "created_at")
    list_filter = ("from_status", "to_status", "created_at")
    search_fields = ("work_item__asset__asset_id", "note", "actor__username")
    readonly_fields = (
        "work_item",
        "from_status",
        "to_status",
        "note",
        "actor",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntegrationRun)
class IntegrationRunAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "status",
        "records_received",
        "identities_matched",
        "work_items_created",
        "started_at",
        "completed_at",
    )
    list_filter = ("provider", "status", "started_at")
    readonly_fields = tuple(field.name for field in IntegrationRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntuneSyncRun)
class IntuneSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "status",
        "records_received",
        "devices_matched",
        "devices_duplicate",
        "devices_unmatched",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "started_at")
    readonly_fields = tuple(field.name for field in IntuneSyncRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntuneDevice)
class IntuneDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "device_name",
        "serial_number",
        "compliance_state",
        "match_status",
        "matched_asset",
        "last_seen_run",
    )
    list_filter = ("match_status", "compliance_state")
    search_fields = (
        "managed_device_id",
        "device_name",
        "serial_number",
        "matched_asset__asset_id",
    )
    readonly_fields = tuple(field.name for field in IntuneDevice._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MaintenanceWorkOrder)
class MaintenanceWorkOrderAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "title",
        "priority",
        "status",
        "vendor",
        "target_date",
        "cost",
        "created_at",
    )
    list_filter = ("status", "priority", "vendor", "created_at")
    search_fields = ("asset__asset_id", "title", "vendor")
    readonly_fields = (
        "status",
        "asset",
        "created_by",
        "created_at",
        "updated_at",
        "completed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MaintenanceWorkOrderEvent)
class MaintenanceWorkOrderEventAdmin(admin.ModelAdmin):
    list_display = ("work_order", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("work_order__asset__asset_id", "work_order__title", "note")
    readonly_fields = tuple(field.name for field in MaintenanceWorkOrderEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "requester",
        "status",
        "quantity",
        "quantity_received",
        "purchase_order_reference",
        "delivery_status",
        "created_at",
    )
    list_filter = ("status", "delivery_status", "created_at")
    search_fields = ("title", "purchase_order_reference", "requester__username")
    readonly_fields = tuple(field.name for field in ProcurementRequest._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcurementQuote)
class ProcurementQuoteAdmin(admin.ModelAdmin):
    list_display = ("request", "supplier", "quote_reference", "unit_cost", "created_at")
    list_filter = ("supplier", "created_at")
    search_fields = ("request__title", "supplier", "quote_reference")
    readonly_fields = tuple(field.name for field in ProcurementQuote._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcurementReceipt)
class ProcurementReceiptAdmin(admin.ModelAdmin):
    list_display = ("request", "receipt_reference", "quantity", "received_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("request__title", "receipt_reference")
    readonly_fields = tuple(field.name for field in ProcurementReceipt._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcurementEvent)
class ProcurementEventAdmin(admin.ModelAdmin):
    list_display = ("request", "event_type", "actor", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("request__title", "details")
    readonly_fields = tuple(field.name for field in ProcurementEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DisposalCase)
class DisposalCaseAdmin(admin.ModelAdmin):
    list_display = ("asset", "method", "status", "requested_by", "created_at", "completed_at")
    list_filter = ("status", "method", "created_at")
    search_fields = ("asset__asset_id", "reason", "disposal_evidence_ref")
    readonly_fields = tuple(field.name for field in DisposalCase._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DisposalEvent)
class DisposalEventAdmin(admin.ModelAdmin):
    list_display = ("case", "event_type", "actor", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("case__asset__asset_id", "note")
    readonly_fields = tuple(field.name for field in DisposalEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SoftwareProduct)
class SoftwareProductAdmin(admin.ModelAdmin):
    list_display = ("name", "publisher", "version", "category", "end_of_support")
    list_filter = ("category", "publisher")
    search_fields = ("name", "publisher", "version")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SoftwareContract)
class SoftwareContractAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "supplier",
        "contract_type",
        "purchased_quantity",
        "end_date",
        "status",
    )
    list_filter = ("contract_type", "status", "auto_renew", "end_date")
    search_fields = ("product__name", "supplier", "contract_reference")
    readonly_fields = tuple(field.name for field in SoftwareContract._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SoftwareLicenseAssignment)
class SoftwareLicenseAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "contract",
        "assignee_ref",
        "department",
        "status",
        "assigned_by",
        "assigned_at",
        "released_at",
    )
    list_filter = ("status", "department", "assigned_at")
    search_fields = ("contract__product__name", "assignee_ref", "department")
    readonly_fields = tuple(
        field.name for field in SoftwareLicenseAssignment._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
