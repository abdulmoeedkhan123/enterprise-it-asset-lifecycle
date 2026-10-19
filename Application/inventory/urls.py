from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("healthz/", views.health_check, name="health-check"),
    path("", views.dashboard, name="dashboard"),
    path("assets/", views.asset_list, name="asset-list"),
    path("assets/new/", views.asset_create, name="asset-create"),
    path("assets/<int:pk>/", views.asset_detail, name="asset-detail"),
    path("assets/<int:pk>/edit/", views.asset_update, name="asset-update"),
    path("assets/<int:pk>/transition/", views.asset_transition, name="asset-transition"),
]
