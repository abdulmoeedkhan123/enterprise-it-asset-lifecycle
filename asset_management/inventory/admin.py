from django.contrib import admin

from .models import Asset, ImportRun, LifecycleEvent


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
