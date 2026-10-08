from django.urls import path

from .views import HubCreateView, HubDetailView, HubListView, HubPerformanceView

app_name = "hubs"

urlpatterns = [
    path("", HubListView.as_view(), name="list"),
    path("create/", HubCreateView.as_view(), name="create"),
    path("<uuid:pk>/performance/", HubPerformanceView.as_view(), name="performance"),
    path("<uuid:pk>/", HubDetailView.as_view(), name="detail"),
]