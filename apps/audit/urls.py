from django.urls import path

from .views import AuditListView, AuditExportView

app_name = "audit"

urlpatterns = [
    path("", AuditListView.as_view(), name="list"),
    path("export/<str:format>/", AuditExportView.as_view(), name="export"),
]