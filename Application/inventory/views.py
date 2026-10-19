from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AssetForm, TransitionForm
from .models import Asset, LifecycleEvent, LifecycleStatus, ReturnWorkItem
from .services import transition_asset


def add_bar_widths(rows: list[dict]) -> list[dict]:
    maximum = max((row["total"] for row in rows), default=0)
    return [
        {**row, "width": round(row["total"] / maximum * 100) if maximum else 0}
        for row in rows
    ]


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unhealthy"}, status=503)
    return JsonResponse({"status": "ok"})


@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def dashboard(request):
    assets = Asset.objects.all()
    status_counts = add_bar_widths(list(
        assets.values("lifecycle_status")
        .annotate(total=Count("pk"))
        .order_by("-total", "lifecycle_status")
    ))
    site_counts = add_bar_widths(list(
        assets.values("site").annotate(total=Count("pk")).order_by("-total", "site")
    ))
    today = timezone.localdate()
    active = assets.exclude(
        lifecycle_status__in=[LifecycleStatus.DISPOSED, LifecycleStatus.LOST_STOLEN]
    )
    context = {
        "asset_count": assets.count(),
        "assigned_count": assets.filter(lifecycle_status=LifecycleStatus.ASSIGNED).count(),
        "overdue_count": assets.filter(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date__lt=today,
        ).count(),
        "expired_warranty_count": active.filter(warranty_end__lt=today).count(),
        "status_counts": status_counts,
        "site_counts": site_counts,
        "report_date": today,
        "review_queue": assets.filter(
            Q(lifecycle_status=LifecycleStatus.RETURN_PENDING, return_due_date__lt=today)
            | Q(lifecycle_status=LifecycleStatus.ASSIGNED, custodian_ref="")
            | (
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
                )
            )
            | Q(
                lifecycle_status=LifecycleStatus.DISPOSED,
                disposal_evidence_ref="",
            )
        ).order_by("asset_id")[:15],
    }
    return render(request, "inventory/dashboard.html", context)


@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def asset_list(request):
    assets = Asset.objects.all()
    selected_site = request.GET.get("site", "").strip()
    selected_status = request.GET.get("status", "").strip()
    search = request.GET.get("q", "").strip()
    if selected_site:
        assets = assets.filter(site=selected_site)
    if selected_status:
        assets = assets.filter(lifecycle_status=selected_status)
    if search:
        assets = assets.filter(
            Q(asset_id__icontains=search)
            | Q(serial_ref__icontains=search)
            | Q(custodian_ref__icontains=search)
            | Q(site__icontains=search)
        )
    paginator = Paginator(assets, 50)
    page = paginator.get_page(request.GET.get("page"))
    context = {
        "page_obj": page,
        "assets": page.object_list,
        "result_count": paginator.count,
        "sites": Asset.objects.order_by("site").values_list("site", flat=True).distinct(),
        "statuses": LifecycleStatus.choices,
        "selected_site": selected_site,
        "selected_status": selected_status,
        "search": search,
    }
    return render(request, "inventory/asset_list.html", context)


@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def asset_detail(request, pk: int):
    asset = get_object_or_404(Asset, pk=pk)
    events = asset.events.select_related("actor")[:50]
    return render(
        request,
        "inventory/asset_detail.html",
        {"asset": asset, "events": events},
    )


@login_required
@permission_required("inventory.add_asset", raise_exception=True)
def asset_create(request):
    form = AssetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            asset = form.save(commit=False)
            asset.lifecycle_status = LifecycleStatus.IN_STOCK
            asset.full_clean()
            asset.save()
            LifecycleEvent.objects.create(
                asset=asset,
                event_type=LifecycleEvent.EventType.CREATED,
                to_status=asset.lifecycle_status,
                reason="Asset record created",
                actor=request.user,
            )
        messages.success(request, f"Asset {asset.asset_id} was created.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    return render(
        request,
        "inventory/asset_form.html",
        {"form": form, "page_title": "Register an asset"},
    )


@login_required
@permission_required("inventory.change_asset", raise_exception=True)
def asset_update(request, pk: int):
    asset = get_object_or_404(Asset, pk=pk)
    original_values = {
        field: getattr(asset, field)
        for field in (
            "asset_type",
            "manufacturer",
            "model",
            "serial_ref",
            "site",
            "department",
            "custodian_ref",
            "purchase_date",
            "warranty_end",
            "return_due_date",
            "sanitisation_required",
            "sanitisation_result",
            "sanitisation_evidence_ref",
            "disposal_evidence_ref",
            "source_last_updated",
        )
    }
    form = AssetForm(request.POST or None, instance=asset)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            updated = form.save(commit=False)
            updated.full_clean()
            updated.save()
            changes = {
                field: {"from": str(old), "to": str(getattr(updated, field))}
                for field, old in original_values.items()
                if old != getattr(updated, field)
            }
            if changes:
                LifecycleEvent.objects.create(
                    asset=updated,
                    event_type=LifecycleEvent.EventType.UPDATED,
                    from_status=updated.lifecycle_status,
                    to_status=updated.lifecycle_status,
                    reason="Asset details updated",
                    details={"changes": changes},
                    actor=request.user,
                )
        messages.success(request, f"Asset {asset.asset_id} was updated.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    return render(
        request,
        "inventory/asset_form.html",
        {"form": form, "page_title": f"Edit {asset.asset_id}", "asset": asset},
    )


@login_required
@permission_required("inventory.transition_asset", raise_exception=True)
def asset_transition(request, pk: int):
    asset = get_object_or_404(Asset, pk=pk)
    form = TransitionForm(request.POST or None, asset=asset)
    if request.method == "POST" and form.is_valid():
        try:
            transition_asset(
                asset_id=asset.pk,
                to_status=form.cleaned_data["to_status"],
                actor=request.user,
                reason=form.cleaned_data["reason"],
                return_due_date=form.cleaned_data.get("return_due_date"),
                sanitisation_result=form.cleaned_data.get("sanitisation_result", ""),
                sanitisation_evidence_ref=form.cleaned_data.get(
                    "sanitisation_evidence_ref", ""
                ),
                disposal_evidence_ref=form.cleaned_data.get("disposal_evidence_ref", ""),
            )
        except (Asset.DoesNotExist, ValidationError) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Asset {asset.asset_id} status was updated.")
            return redirect("inventory:asset-detail", pk=asset.pk)
    return render(
        request,
        "inventory/transition_form.html",
        {"form": form, "asset": asset},
    )


@login_required
@permission_required("inventory.view_returnworkitem", raise_exception=True)
def return_work_queue(request):
    selected_status = request.GET.get("status", "").strip()
    work_items = ReturnWorkItem.objects.select_related("asset")
    valid_statuses = {value for value, _label in ReturnWorkItem.Status.choices}
    if selected_status in valid_statuses:
        work_items = work_items.filter(status=selected_status)
    elif selected_status != "all":
        selected_status = "open"
        work_items = work_items.filter(status=ReturnWorkItem.Status.OPEN)
    return render(
        request,
        "inventory/return_work_queue.html",
        {
            "work_items": work_items[:100],
            "statuses": ReturnWorkItem.Status.choices,
            "selected_status": selected_status,
        },
    )
