from django.urls import path

from .views import HubCreateView, HubListView

app_name = "hubs"

urlpatterns = [
    path("", HubListView.as_view(), name="list"),
    path("create/", HubCreateView.as_view(), name="create"),
]