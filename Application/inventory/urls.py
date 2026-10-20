from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("healthz/", views.health_check, name="health-check"),
    path("", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("copilot/", views.copilot, name="copilot"),
    path("settings/", views.application_settings, name="application-settings"),
    path("assets/barcode-lookup/", views.asset_barcode_lookup, name="asset-barcode-lookup"),
    path("assets/", views.asset_list, name="asset-list"),
    path("assets/new/", views.asset_create, name="asset-create"),
    path("assets/<int:pk>/", views.asset_detail, name="asset-detail"),
    path("assets/<int:pk>/edit/", views.asset_update, name="asset-update"),
    path("assets/<int:pk>/transition/", views.asset_transition, name="asset-transition"),
    path(
        "assets/<int:asset_pk>/maintenance/new/",
        views.maintenance_work_order_create,
        name="maintenance-work-order-create",
    ),
    path(
        "maintenance/",
        views.maintenance_work_orders,
        name="maintenance-work-orders",
    ),
    path(
        "maintenance/<int:pk>/status/",
        views.maintenance_work_order_update,
        name="maintenance-work-order-update",
    ),
    path("procurement/", views.procurement_list, name="procurement-list"),
    path("procurement/new/", views.procurement_create, name="procurement-create"),
    path("procurement/<int:pk>/", views.procurement_detail, name="procurement-detail"),
    path(
        "procurement/<int:pk>/quotes/add/",
        views.procurement_quote_add,
        name="procurement-quote-add",
    ),
    path(
        "procurement/<int:pk>/quotes/<int:quote_pk>/select/",
        views.procurement_quote_select,
        name="procurement-quote-select",
    ),
    path(
        "procurement/<int:pk>/submit/",
        views.procurement_submit,
        name="procurement-submit",
    ),
    path(
        "procurement/<int:pk>/cancel/",
        views.procurement_cancel,
        name="procurement-cancel",
    ),
    path(
        "procurement/<int:pk>/review/",
        views.procurement_review,
        name="procurement-review",
    ),
    path(
        "procurement/<int:pk>/order/",
        views.procurement_order,
        name="procurement-order",
    ),
    path(
        "procurement/<int:pk>/delivery/",
        views.procurement_delivery_update,
        name="procurement-delivery-update",
    ),
    path(
        "procurement/<int:pk>/receive/",
        views.procurement_receive,
        name="procurement-receive",
    ),
    path("disposals/", views.disposal_list, name="disposal-list"),
    path(
        "assets/<int:asset_pk>/disposal/new/",
        views.disposal_create,
        name="disposal-create",
    ),
    path(
        "disposals/<int:pk>/review/",
        views.disposal_review,
        name="disposal-review",
    ),
    path(
        "disposals/<int:pk>/complete/",
        views.disposal_complete,
        name="disposal-complete",
    ),
    path("returns/", views.return_work_queue, name="return-work-queue"),
    path(
        "returns/<int:pk>/update/",
        views.return_work_item_update,
        name="return-work-item-update",
    ),
    path("integrations/", views.integration_catalog, name="integration-catalog"),
    path("integrations/intune/", views.intune_devices, name="intune-devices"),
    path("software/", views.software_catalog, name="software-catalog"),
    path("software/new/", views.software_product_create, name="software-create"),
    path(
        "software/renewals/",
        views.software_renewals,
        name="software-renewals",
    ),
    path(
        "software/<int:pk>/",
        views.software_product_detail,
        name="software-detail",
    ),
    path(
        "software/<int:product_pk>/contracts/new/",
        views.software_contract_create,
        name="software-contract-create",
    ),
    path(
        "software/contracts/<int:contract_pk>/assign/",
        views.software_license_assign,
        name="software-license-assign",
    ),
    path(
        "software/contracts/<int:contract_pk>/assignments/<int:assignment_pk>/release/",
        views.software_license_release,
        name="software-license-release",
    ),
]
