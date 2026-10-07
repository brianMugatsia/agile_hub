from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.LandingPageView.as_view(), name="home"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("settings/", views.SettingsHomeView.as_view(), name="settings"),
]