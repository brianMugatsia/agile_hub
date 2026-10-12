from django.urls import path

from apps.core.spreadsheets import (
    MemberImportTemplateView,
    MemberImportView,
    BusinessImportTemplateView,
    BusinessImportView,
)
from .views import (
    MemberCreateView,
    MemberDetailView,
    MemberListView,
    MemberUpdateView,
    ContributionCreateView,
    ContributionListView,
    ContributionUpdateView,
)

app_name = "members"

urlpatterns = [
    path("", MemberListView.as_view(), name="list"),
    path("create/", MemberCreateView.as_view(), name="create"),
    path("import/", MemberImportView.as_view(), name="import"),
    path("import/template/", MemberImportTemplateView.as_view(), name="import_template"),
    path("<int:pk>/", MemberDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", MemberUpdateView.as_view(), name="edit"),
    path("contributions/", ContributionListView.as_view(), name="contributions"),
    path("contributions/create/", ContributionCreateView.as_view(), name="contribution_create"),
    path("contributions/import/", BusinessImportView.as_view(), name="contribution_import"),
    path("contributions/import/template/", BusinessImportTemplateView.as_view(), name="contribution_import_template"),
    path("contributions/<int:pk>/edit/", ContributionUpdateView.as_view(), name="contribution_edit"),
]
