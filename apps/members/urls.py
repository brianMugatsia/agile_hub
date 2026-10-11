from django.urls import path

from .views import (
    MemberCreateView,
    MemberDetailView,
    MemberListView,
    MemberUpdateView,
    BusinessCreateView,
    BusinessListView,
    BusinessUpdateView,
)

app_name = "members"

urlpatterns = [
    path("", MemberListView.as_view(), name="list"),
    path("create/", MemberCreateView.as_view(), name="create"),
    path("<int:pk>/", MemberDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", MemberUpdateView.as_view(), name="edit"),
    path("businesses/", BusinessListView.as_view(), name="businesses"),
    path("businesses/create/", BusinessCreateView.as_view(), name="business_create"),
    path("businesses/<int:pk>/edit/", BusinessUpdateView.as_view(), name="business_edit"),
]
