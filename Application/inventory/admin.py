from django.contrib import admin
from django.db import transaction

from .models import (
    Asset,
    IdentityLink,
    ImportRun,
    IntegrationRun,
    LifecycleEvent,
    ReturnWorkItem,
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
    readonly_fields = ("created_at", "updated_at", "lifecycle_status")
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
