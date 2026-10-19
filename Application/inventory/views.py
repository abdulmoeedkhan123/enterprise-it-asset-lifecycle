from __future__ import annotations

from datetime import date
from typing import TypedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from django.utils import timezone

from .forms import (
    AssetForm,
    DisposalCompletionForm,
    DisposalRequestForm,
    DisposalReviewForm,
    MaintenanceStatusForm,
    MaintenanceWorkOrderForm,
    ProcurementDecisionForm,
    ProcurementDeliveryUpdateForm,
    ProcurementQuoteForm,
    ProcurementReceiptForm,
    ProcurementRequestForm,
    PurchaseOrderForm,
    TransitionForm,
)
from .integrations.catalog import INTEGRATION_CATALOG
from .models import (
    Asset,
    DisposalCase,
    DisposalEvent,
    ImportRun,
    IntegrationRun,
    LifecycleEvent,
    LifecycleStatus,
    MaintenanceWorkOrder,
    MaintenanceWorkOrderEvent,
    ProcurementEvent,
    ProcurementQuote,
    ProcurementReceipt,
    ProcurementRequest,
    ReturnWorkItem,
)
from .notifications import build_asset_notifications
from .reporting import build_asset_quality_report
from .services import transition_asset


class IntegrationCatalogEntry(TypedDict):
    name: str
    category: str
    availability: str
    protocol: str
    workflow: str
    data_direction: str
    notes: str


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
@require_GET
def asset_barcode_lookup(request):
    code = request.GET.get("code", "").strip()
    if not code or len(code) > 64:
        return JsonResponse({"error": "Provide a barcode value up to 64 characters."}, status=400)
    matches = Asset.objects.filter(Q(asset_id=code) | Q(serial_ref=code)).order_by(
        "asset_id"
    )[:10]
    return JsonResponse(
        {
            "matches": [
                {
                    "asset_id": asset.asset_id,
                    "site": asset.site,
                    "status": asset.lifecycle_status,
                    "url": reverse("inventory:asset-detail", args=[asset.pk]),
                }
                for asset in matches
            ]
        }
    )


@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def dashboard(request):
    all_assets = Asset.objects.all()
    sites = list(all_assets.order_by("site").values_list("site", flat=True).distinct())
    selected_site = request.GET.get("site", "").strip()
    selected_status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, _label in LifecycleStatus.choices}
    if selected_site not in sites:
        selected_site = ""
    if selected_status not in valid_statuses:
        selected_status = ""
    assets = all_assets
    if selected_site:
        assets = assets.filter(site=selected_site)
    if selected_status:
        assets = assets.filter(lifecycle_status=selected_status)
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
        "sites": sites,
        "statuses": LifecycleStatus.choices,
        "selected_site": selected_site,
        "selected_status": selected_status,
        "quality_report": build_asset_quality_report(assets, as_of=today),
        "recent_import_runs": ImportRun.objects.all()[:5],
        "recent_integration_runs": IntegrationRun.objects.all()[:5],
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
def notifications(request):
    page = Paginator(build_asset_notifications(), 50).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "inventory/notifications.html",
        {
            "notifications": page.object_list,
            "notification_page": page,
        },
    )


@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def asset_detail(request, pk: int):
    asset = get_object_or_404(Asset, pk=pk)
    events = asset.events.select_related("actor")[:50]
    return render(
        request,
        "inventory/asset_detail.html",
        {
            "asset": asset,
            "events": events,
            "maintenance_orders": asset.maintenance_orders.select_related(
                "created_by"
            ).prefetch_related("events__actor")[:5],
        },
    )


@login_required
@permission_required("inventory.view_maintenanceworkorder", raise_exception=True)
def maintenance_work_orders(request):
    work_orders = MaintenanceWorkOrder.objects.select_related("asset", "created_by")
    selected_status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, _label in MaintenanceWorkOrder.Status.choices}
    if selected_status in valid_statuses:
        work_orders = work_orders.filter(status=selected_status)
    elif selected_status != "all":
        selected_status = MaintenanceWorkOrder.Status.OPEN
        work_orders = work_orders.filter(status=selected_status)
    page = Paginator(work_orders, 50).get_page(request.GET.get("page"))
    for order in page.object_list:
        order.status_form = MaintenanceStatusForm(work_order=order)
    return render(
        request,
        "inventory/maintenance_work_orders.html",
        {
            "work_orders": page.object_list,
            "work_order_page": page,
            "statuses": MaintenanceWorkOrder.Status.choices,
            "selected_status": selected_status,
        },
    )


@login_required
@permission_required(
    ("inventory.add_maintenanceworkorder", "inventory.view_maintenanceworkorder"),
    raise_exception=True,
)
def maintenance_work_order_create(request, asset_pk: int):
    asset = get_object_or_404(Asset, pk=asset_pk)
    if asset.lifecycle_status in {
        LifecycleStatus.DISPOSED,
        LifecycleStatus.LOST_STOLEN,
    }:
        messages.error(request, "Maintenance work orders cannot be opened for this asset.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    form = MaintenanceWorkOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            work_order = form.save(commit=False)
            work_order.asset = asset
            work_order.created_by = request.user
            work_order.save()
            MaintenanceWorkOrderEvent.objects.create(
                work_order=work_order,
                to_status=work_order.status,
                note="Work order created.",
                actor=request.user,
            )
        messages.success(request, f"Work order for {asset.asset_id} was created.")
        return redirect("inventory:maintenance-work-orders")
    return render(
        request,
        "inventory/maintenance_work_order_form.html",
        {"form": form, "asset": asset},
    )


@login_required
@permission_required(
    ("inventory.change_maintenanceworkorder", "inventory.view_maintenanceworkorder"),
    raise_exception=True,
)
@require_POST
def maintenance_work_order_update(request, pk: int):
    with transaction.atomic():
        work_order = get_object_or_404(
            MaintenanceWorkOrder.objects.select_for_update(), pk=pk
        )
        form = MaintenanceStatusForm(request.POST, work_order=work_order)
        if form.is_valid():
            old_status = work_order.status
            work_order.status = form.cleaned_data["status"]
            work_order.save(update_fields=("status", "updated_at"))
            MaintenanceWorkOrderEvent.objects.create(
                work_order=work_order,
                from_status=old_status,
                to_status=work_order.status,
                note="Work order status updated.",
                actor=request.user,
            )
            messages.success(
                request,
                f"Work order for {work_order.asset.asset_id} was updated.",
            )
        else:
            messages.error(request, "That status update is not allowed.")
    return redirect("inventory:maintenance-work-orders")


@login_required
@permission_required("inventory.view_procurementrequest", raise_exception=True)
def procurement_list(request):
    requests = ProcurementRequest.objects.select_related("requester", "selected_quote")
    if not request.user.has_perm("inventory.view_all_procurementrequests"):
        requests = requests.filter(requester=request.user)
    selected_status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, _label in ProcurementRequest.Status.choices}
    if selected_status in valid_statuses:
        requests = requests.filter(status=selected_status)
    elif selected_status != "all":
        selected_status = "all"
    page = Paginator(requests, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "inventory/procurement_list.html",
        {
            "procurement_requests": page.object_list,
            "procurement_page": page,
            "statuses": ProcurementRequest.Status.choices,
            "selected_status": selected_status,
        },
    )


@login_required
@permission_required(
    ("inventory.add_procurementrequest", "inventory.view_procurementrequest"),
    raise_exception=True,
)
def procurement_create(request):
    form = ProcurementRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            purchase_request = form.save(commit=False)
            purchase_request.requester = request.user
            purchase_request.save()
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.CREATED,
                actor=request.user,
            )
        messages.success(request, "Procurement request saved as a draft.")
        return redirect(
            "inventory:procurement-detail",
            pk=purchase_request.pk,
        )
    return render(
        request,
        "inventory/procurement_form.html",
        {"form": form},
    )


@login_required
@permission_required("inventory.view_procurementrequest", raise_exception=True)
def procurement_detail(request, pk: int):
    purchase_request = get_object_or_404(
        ProcurementRequest.objects.select_related(
            "requester", "selected_quote"
        ).prefetch_related("quotes", "events__actor", "registered_assets"),
        pk=pk,
    )
    if (
        purchase_request.requester_id != request.user.pk
        and not request.user.has_perm("inventory.view_all_procurementrequests")
    ):
        raise PermissionDenied
    return render(
        request,
        "inventory/procurement_detail.html",
        {
            "purchase_request": purchase_request,
            "quotes": purchase_request.quotes.all(),
            "events": purchase_request.events.select_related("actor").all(),
            "quote_form": ProcurementQuoteForm(),
            "decision_form": ProcurementDecisionForm(),
            "purchase_order_form": PurchaseOrderForm(),
            "receipt_form": ProcurementReceiptForm(),
            "delivery_form": ProcurementDeliveryUpdateForm(),
            "can_manage_draft": _procurement_owner_or_changer(
                request, purchase_request
            ),
            "quoted_total": (
                purchase_request.selected_quote.unit_cost * purchase_request.quantity
                if purchase_request.selected_quote_id
                else None
            ),
            "remaining_to_receive": max(
                purchase_request.quantity - purchase_request.quantity_received,
                0,
            ),
            "receipts": purchase_request.receipts.select_related("received_by").all(),
            "remaining_to_register": max(
                purchase_request.quantity_received
                - purchase_request.registered_assets.count(),
                0,
            ),
        },
    )


def _procurement_owner_or_changer(request, purchase_request) -> bool:
    return (
        purchase_request.requester_id == request.user.pk
        or (
            request.user.has_perm("inventory.change_procurementrequest")
            and request.user.has_perm("inventory.view_all_procurementrequests")
        )
    )


@login_required
@permission_required("inventory.view_procurementrequest", raise_exception=True)
@require_POST
def procurement_quote_add(request, pk: int):
    form = ProcurementQuoteForm(request.POST)
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        if (
            purchase_request.status != ProcurementRequest.Status.DRAFT
            or not _procurement_owner_or_changer(request, purchase_request)
        ):
            messages.error(request, "Only the requester may add quotes to a draft.")
        elif form.is_valid():
            if purchase_request.quotes.filter(
                supplier=form.cleaned_data["supplier"],
                quote_reference=form.cleaned_data["quote_reference"],
            ).exists():
                messages.error(request, "That supplier quote reference is already recorded.")
            else:
                quote = form.save(commit=False)
                quote.request = purchase_request
                quote.save()
                ProcurementEvent.objects.create(
                    request=purchase_request,
                    event_type=ProcurementEvent.EventType.QUOTE_ADDED,
                    actor=request.user,
                    details={"supplier": quote.supplier, "unit_cost": str(quote.unit_cost)},
                )
                messages.success(request, f"Quote from {quote.supplier} was added.")
        else:
            messages.error(request, form.errors.as_text())
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required("inventory.view_procurementrequest", raise_exception=True)
@require_POST
def procurement_quote_select(request, pk: int, quote_pk: int):
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        quote = get_object_or_404(
            ProcurementQuote, pk=quote_pk, request=purchase_request
        )
        if (
            purchase_request.status != ProcurementRequest.Status.DRAFT
            or not _procurement_owner_or_changer(request, purchase_request)
        ):
            messages.error(request, "A quote can only be selected by the requester on a draft.")
        else:
            purchase_request.selected_quote = quote
            purchase_request.save(update_fields=("selected_quote", "updated_at"))
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.QUOTE_SELECTED,
                actor=request.user,
                details={"supplier": quote.supplier, "unit_cost": str(quote.unit_cost)},
            )
            messages.success(request, f"{quote.supplier} was selected for review.")
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required("inventory.view_procurementrequest", raise_exception=True)
@require_POST
def procurement_submit(request, pk: int):
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        if (
            purchase_request.status != ProcurementRequest.Status.DRAFT
            or not _procurement_owner_or_changer(request, purchase_request)
        ):
            messages.error(request, "Only the requester may submit a draft request.")
        elif not purchase_request.selected_quote_id:
            messages.error(request, "Select a supplier quote before requesting approval.")
        else:
            purchase_request.status = ProcurementRequest.Status.PENDING_APPROVAL
            purchase_request.submitted_at = timezone.now()
            purchase_request.save(
                update_fields=("status", "submitted_at", "updated_at")
            )
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.SUBMITTED,
                actor=request.user,
            )
            messages.success(request, "Request submitted for independent approval.")
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required("inventory.view_procurementrequest", raise_exception=True)
@require_POST
def procurement_cancel(request, pk: int):
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        cancellable_statuses = {
            ProcurementRequest.Status.DRAFT,
            ProcurementRequest.Status.PENDING_APPROVAL,
            ProcurementRequest.Status.APPROVED,
        }
        if (
            purchase_request.status not in cancellable_statuses
            or not _procurement_owner_or_changer(request, purchase_request)
        ):
            messages.error(request, "This request cannot be withdrawn.")
        else:
            purchase_request.status = ProcurementRequest.Status.CANCELLED
            purchase_request.save(update_fields=("status", "updated_at"))
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.CANCELLED,
                actor=request.user,
            )
            messages.success(request, "Procurement request withdrawn.")
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required(
    (
        "inventory.approve_procurementrequest",
        "inventory.view_all_procurementrequests",
    ),
    raise_exception=True,
)
@require_POST
def procurement_review(request, pk: int):
    form = ProcurementDecisionForm(request.POST)
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        if purchase_request.status != ProcurementRequest.Status.PENDING_APPROVAL:
            messages.error(request, "This request is not awaiting approval.")
        elif purchase_request.requester_id == request.user.pk:
            messages.error(request, "Requesters cannot approve their own request.")
        elif not form.is_valid():
            messages.error(request, form.errors.as_text())
        else:
            approved = form.cleaned_data["decision"] == "approve"
            purchase_request.status = (
                ProcurementRequest.Status.APPROVED
                if approved
                else ProcurementRequest.Status.REJECTED
            )
            purchase_request.save(update_fields=("status", "updated_at"))
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=(
                    ProcurementEvent.EventType.APPROVED
                    if approved
                    else ProcurementEvent.EventType.REJECTED
                ),
                actor=request.user,
                details={"note": form.cleaned_data["note"]},
            )
            messages.success(
                request,
                "Request approved." if approved else "Request rejected.",
            )
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required(
    (
        "inventory.manage_procurementrequest",
        "inventory.view_all_procurementrequests",
    ),
    raise_exception=True,
)
@require_POST
def procurement_order(request, pk: int):
    form = PurchaseOrderForm(request.POST)
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update().select_related(
                "selected_quote"
            ),
            pk=pk,
        )
        if purchase_request.status != ProcurementRequest.Status.APPROVED:
            messages.error(request, "Only approved requests can be ordered.")
        elif not purchase_request.selected_quote_id:
            messages.error(request, "An approved request must have a selected supplier quote.")
        elif not form.is_valid():
            messages.error(request, form.errors.as_text())
        else:
            purchase_request.status = ProcurementRequest.Status.ORDERED
            purchase_request.purchase_order_reference = form.cleaned_data[
                "purchase_order_reference"
            ]
            purchase_request.expected_delivery_date = form.cleaned_data[
                "expected_delivery_date"
            ]
            purchase_request.tracking_reference = form.cleaned_data[
                "tracking_reference"
            ]
            purchase_request.delivery_status = (
                ProcurementRequest.DeliveryStatus.ORDERED
            )
            purchase_request.save(
                update_fields=(
                    "status",
                    "purchase_order_reference",
                    "expected_delivery_date",
                    "tracking_reference",
                    "delivery_status",
                    "updated_at",
                )
            )
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.ORDERED,
                actor=request.user,
                details={
                    "purchase_order_reference": purchase_request.purchase_order_reference,
                    "supplier": purchase_request.selected_quote.supplier,
                    "expected_delivery_date": (
                        purchase_request.expected_delivery_date.isoformat()
                        if purchase_request.expected_delivery_date
                        else ""
                    ),
                    "tracking_reference": purchase_request.tracking_reference,
                },
            )
            messages.success(request, "Purchase order recorded.")
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required(
    (
        "inventory.manage_procurementrequest",
        "inventory.view_all_procurementrequests",
    ),
    raise_exception=True,
)
@require_POST
def procurement_delivery_update(request, pk: int):
    form = ProcurementDeliveryUpdateForm(request.POST)
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        if purchase_request.status not in {
            ProcurementRequest.Status.ORDERED,
            ProcurementRequest.Status.PARTIALLY_RECEIVED,
        }:
            messages.error(request, "Delivery tracking is available after an order is placed.")
        elif not form.is_valid():
            messages.error(request, form.errors.as_text())
        else:
            purchase_request.delivery_status = form.cleaned_data["delivery_status"]
            purchase_request.expected_delivery_date = (
                form.cleaned_data["expected_delivery_date"]
                or purchase_request.expected_delivery_date
            )
            purchase_request.tracking_reference = (
                form.cleaned_data["tracking_reference"]
                or purchase_request.tracking_reference
            )
            purchase_request.save(
                update_fields=(
                    "delivery_status",
                    "expected_delivery_date",
                    "tracking_reference",
                    "updated_at",
                )
            )
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.DELIVERY_UPDATED,
                actor=request.user,
                details={
                    "delivery_status": purchase_request.delivery_status,
                    "expected_delivery_date": (
                        purchase_request.expected_delivery_date.isoformat()
                        if purchase_request.expected_delivery_date
                        else ""
                    ),
                    "tracking_reference": purchase_request.tracking_reference,
                },
            )
            messages.success(request, "Delivery tracking was updated.")
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required(
    (
        "inventory.manage_procurementrequest",
        "inventory.view_all_procurementrequests",
    ),
    raise_exception=True,
)
@require_POST
def procurement_receive(request, pk: int):
    form = ProcurementReceiptForm(request.POST)
    with transaction.atomic():
        purchase_request = get_object_or_404(
            ProcurementRequest.objects.select_for_update(),
            pk=pk,
        )
        if purchase_request.status not in {
            ProcurementRequest.Status.ORDERED,
            ProcurementRequest.Status.PARTIALLY_RECEIVED,
        }:
            messages.error(request, "Only an open purchase order can be received.")
        elif not form.is_valid():
            messages.error(request, form.errors.as_text())
        elif ProcurementReceipt.objects.filter(
            request=purchase_request,
            receipt_reference=form.cleaned_data["receipt_reference"],
        ).exists():
            messages.error(request, "That receipt reference has already been recorded.")
        elif (
            purchase_request.quantity_received + form.cleaned_data["quantity"]
            > purchase_request.quantity
        ):
            messages.error(request, "Received quantity cannot exceed the requested amount.")
        else:
            received_now = form.cleaned_data["quantity"]
            ProcurementReceipt.objects.create(
                request=purchase_request,
                receipt_reference=form.cleaned_data["receipt_reference"],
                quantity=received_now,
                received_by=request.user,
            )
            purchase_request.quantity_received += received_now
            complete = purchase_request.quantity_received == purchase_request.quantity
            purchase_request.status = (
                ProcurementRequest.Status.RECEIVED
                if complete
                else ProcurementRequest.Status.PARTIALLY_RECEIVED
            )
            purchase_request.delivery_status = (
                ProcurementRequest.DeliveryStatus.RECEIVED
                if complete
                else ProcurementRequest.DeliveryStatus.PARTIALLY_RECEIVED
            )
            if complete:
                purchase_request.completed_at = timezone.now()
            purchase_request.save(
                update_fields=(
                    "quantity_received",
                    "status",
                    "delivery_status",
                    "completed_at",
                    "updated_at",
                )
            )
            ProcurementEvent.objects.create(
                request=purchase_request,
                event_type=ProcurementEvent.EventType.RECEIVED,
                actor=request.user,
                details={
                    "quantity": received_now,
                    "receipt_reference": form.cleaned_data["receipt_reference"],
                    "quantity_received_total": purchase_request.quantity_received,
                },
            )
            messages.success(request, f"Recorded receipt of {received_now} item(s).")
    return redirect("inventory:procurement-detail", pk=pk)


@login_required
@permission_required("inventory.view_disposalcase", raise_exception=True)
def disposal_list(request):
    cases = DisposalCase.objects.select_related("asset", "requested_by").prefetch_related(
        "events__actor"
    )
    selected_status = request.GET.get("status", "").strip()
    valid_statuses = {value for value, _label in DisposalCase.Status.choices}
    if selected_status in valid_statuses:
        cases = cases.filter(status=selected_status)
    elif selected_status != "all":
        selected_status = DisposalCase.Status.PENDING_APPROVAL
        cases = cases.filter(status=selected_status)
    page = Paginator(cases, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "inventory/disposal_list.html",
        {
            "disposal_cases": page.object_list,
            "disposal_page": page,
            "statuses": DisposalCase.Status.choices,
            "selected_status": selected_status,
        },
    )


@login_required
@permission_required(
    ("inventory.add_disposalcase", "inventory.view_disposalcase"),
    raise_exception=True,
)
def disposal_create(request, asset_pk: int):
    asset = get_object_or_404(Asset, pk=asset_pk)
    if asset.lifecycle_status != LifecycleStatus.READY_FOR_DISPOSAL:
        messages.error(request, "Move this asset to Ready for Disposal before requesting disposal.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    active_statuses = [
        DisposalCase.Status.PENDING_APPROVAL,
        DisposalCase.Status.APPROVED,
    ]
    if DisposalCase.objects.filter(asset=asset, status__in=active_statuses).exists():
        messages.error(request, "An active disposal request already exists for this asset.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    form = DisposalRequestForm(request.POST or None, asset=asset)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked_asset = get_object_or_404(
                    Asset.objects.select_for_update(),
                    pk=asset.pk,
                )
                if DisposalCase.objects.filter(
                    asset=locked_asset,
                    status__in=active_statuses,
                ).exists():
                    messages.error(
                        request,
                        "An active disposal request already exists for this asset.",
                    )
                    return redirect("inventory:asset-detail", pk=asset.pk)
                case = form.save(commit=False)
                case.asset = locked_asset
                case.requested_by = request.user
                case.full_clean()
                case.save()
                DisposalEvent.objects.create(
                    case=case,
                    event_type=DisposalEvent.EventType.REQUESTED,
                    actor=request.user,
                )
        except IntegrityError:
            messages.error(
                request,
                "An active disposal request already exists for this asset.",
            )
            return redirect("inventory:asset-detail", pk=asset.pk)
        messages.success(request, f"Disposal request for {asset.asset_id} was submitted.")
        return redirect("inventory:disposal-list")
    return render(
        request,
        "inventory/disposal_form.html",
        {"form": form, "asset": asset},
    )


@login_required
@permission_required(
    ("inventory.approve_disposalcase", "inventory.view_disposalcase"),
    raise_exception=True,
)
@require_POST
def disposal_review(request, pk: int):
    form = DisposalReviewForm(request.POST)
    with transaction.atomic():
        case = get_object_or_404(DisposalCase.objects.select_for_update(), pk=pk)
        if case.status != DisposalCase.Status.PENDING_APPROVAL:
            messages.error(request, "This disposal request is not awaiting approval.")
        elif case.requested_by_id == request.user.pk:
            messages.error(request, "Requesters cannot approve their own disposal.")
        elif not form.is_valid():
            messages.error(request, form.errors.as_text())
        else:
            approved = form.cleaned_data["decision"] == "approve"
            case.status = (
                DisposalCase.Status.APPROVED
                if approved
                else DisposalCase.Status.REJECTED
            )
            case.save(update_fields=("status", "updated_at"))
            DisposalEvent.objects.create(
                case=case,
                event_type=(
                    DisposalEvent.EventType.APPROVED
                    if approved
                    else DisposalEvent.EventType.REJECTED
                ),
                actor=request.user,
                note=form.cleaned_data["note"],
            )
            messages.success(
                request,
                "Disposal approved." if approved else "Disposal rejected.",
            )
    return redirect("inventory:disposal-list")


@login_required
@permission_required(
    ("inventory.complete_disposalcase", "inventory.view_disposalcase"),
    raise_exception=True,
)
@require_POST
def disposal_complete(request, pk: int):
    form = DisposalCompletionForm(request.POST)
    with transaction.atomic():
        case = get_object_or_404(
            DisposalCase.objects.select_for_update().select_related("asset"),
            pk=pk,
        )
        if case.status != DisposalCase.Status.APPROVED:
            messages.error(request, "Only an approved disposal request can be completed.")
        elif case.events.filter(
            event_type=DisposalEvent.EventType.APPROVED,
            actor=request.user,
        ).exists():
            messages.error(
                request,
                "The disposal approver cannot also complete the disposal.",
            )
        elif not form.is_valid():
            messages.error(request, form.errors.as_text())
        else:
            evidence_ref = form.cleaned_data["disposal_evidence_ref"]
            try:
                transition_asset(
                    asset_id=case.asset_id,
                    to_status=LifecycleStatus.DISPOSED,
                    actor=request.user,
                    reason=f"Approved disposal case {case.pk} completed.",
                    sanitisation_result=case.sanitisation_result,
                    sanitisation_evidence_ref=case.sanitisation_evidence_ref,
                    disposal_evidence_ref=evidence_ref,
                )
            except (Asset.DoesNotExist, ValidationError) as error:
                messages.error(request, str(error))
            else:
                case.disposal_evidence_ref = evidence_ref
                case.status = DisposalCase.Status.COMPLETED
                case.completed_at = timezone.now()
                case.save(
                    update_fields=(
                        "disposal_evidence_ref",
                        "status",
                        "completed_at",
                        "updated_at",
                    )
                )
                DisposalEvent.objects.create(
                    case=case,
                    event_type=DisposalEvent.EventType.COMPLETED,
                    actor=request.user,
                    note=f"Evidence: {evidence_ref}",
                )
                messages.success(request, "Approved disposal completed with evidence.")
    return redirect("inventory:disposal-list")


@login_required
@permission_required(("inventory.add_asset", "inventory.view_asset"), raise_exception=True)
def asset_create(request):
    procurement_id = request.GET.get("procurement_id") or request.POST.get(
        "procurement_id", ""
    )
    purchase_request = None
    if procurement_id:
        purchase_request = get_object_or_404(ProcurementRequest, pk=procurement_id)
        if (
            purchase_request.status
            not in {
                ProcurementRequest.Status.PARTIALLY_RECEIVED,
                ProcurementRequest.Status.RECEIVED,
            }
            or purchase_request.quantity_received
            <= purchase_request.registered_assets.count()
        ):
            messages.error(
                request,
                "Only received items not yet registered can be added to the asset register.",
            )
            return redirect("inventory:procurement-detail", pk=purchase_request.pk)
    form = AssetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if purchase_request:
                purchase_request = get_object_or_404(
                    ProcurementRequest.objects.select_for_update(),
                    pk=purchase_request.pk,
                )
                if (
                    purchase_request.status
                    not in {
                        ProcurementRequest.Status.PARTIALLY_RECEIVED,
                        ProcurementRequest.Status.RECEIVED,
                    }
                    or purchase_request.quantity_received
                    <= purchase_request.registered_assets.count()
                ):
                    messages.error(request, "There are no unregistered received items remaining.")
                    return redirect(
                        "inventory:procurement-detail",
                        pk=purchase_request.pk,
                    )
            asset = form.save(commit=False)
            asset.lifecycle_status = LifecycleStatus.IN_STOCK
            asset.procurement_request = purchase_request
            asset.full_clean()
            asset.save()
            LifecycleEvent.objects.create(
                asset=asset,
                event_type=LifecycleEvent.EventType.CREATED,
                to_status=asset.lifecycle_status,
                reason="Asset record created",
                actor=request.user,
                details=(
                    {"procurement_request_id": purchase_request.pk}
                    if purchase_request
                    else {}
                ),
            )
            if purchase_request:
                ProcurementEvent.objects.create(
                    request=purchase_request,
                    event_type=ProcurementEvent.EventType.ASSET_REGISTERED,
                    actor=request.user,
                    details={"asset_id": asset.asset_id},
                )
        messages.success(request, f"Asset {asset.asset_id} was created.")
        return redirect("inventory:asset-detail", pk=asset.pk)
    return render(
        request,
        "inventory/asset_form.html",
        {
            "form": form,
            "page_title": "Register an asset",
            "purchase_request": purchase_request,
        },
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


@login_required
@permission_required("inventory.view_asset", raise_exception=True)
def integration_catalog(request):
    categories: dict[str, list[IntegrationCatalogEntry]] = {}
    for integration in INTEGRATION_CATALOG:
        categories.setdefault(integration["category"], []).append(integration)
    return render(
        request,
        "inventory/integration_catalog.html",
        {"integration_categories": categories.items()},
    )
