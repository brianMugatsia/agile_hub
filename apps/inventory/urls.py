from django.urls import path

from .views import InventoryListView, StockMovementCreateView

app_name = "inventory"

urlpatterns = [
    path("", InventoryListView.as_view(), name="list"),
    path("movement/create/", StockMovementCreateView.as_view(), name="movement_create"),
]