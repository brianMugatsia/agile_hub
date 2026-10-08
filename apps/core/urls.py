from django.urls import path

from . import views
from .saved_filters import DeleteFilterView, SaveFilterView

app_name = "core"

urlpatterns = [
    path("", views.LandingPageView.as_view(), name="home"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("settings/", views.SettingsHomeView.as_view(), name="settings"),
    path("saved-filters/", SaveFilterView.as_view(), name="saved_filter_create"),
    path("saved-filters/<int:pk>/delete/", DeleteFilterView.as_view(), name="saved_filter_delete"),
]