from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView

from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView
from apps.core.mixins import ActiveHubInitialMixin, PageMixin
from apps.core.scoping import scope_queryset

from .forms import MemberProfileForm, BusinessForm
from .models import MemberProfile, Business


class MemberListView(ScopedModelListView):
    model = MemberProfile
    page_title = "Members"
    columns = (
        {"label": "Name", "field": "user__display_name"},
        {"label": "Email", "field": "user__email"},
        {"label": "Phone", "field": "phone_number"},
        {"label": "Hub", "field": "hub__name"},
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone_number")
    create_url_name = "members:create"
    create_label = "Add member"
    create_permission = "members.add_memberprofile"
    row_edit_url_name = "members:edit"
    row_edit_permission = "members.change_memberprofile"
    filter_hub = True


class MemberDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = MemberProfile
    template_name = "members/member_detail.html"
    context_object_name = "member"
    permission_required = "members.view_memberprofile"
    page_title = "Member details"

    def get_queryset(self):
        return scope_queryset(
            MemberProfile.objects.select_related("user", "hub"),
            self.request.user,
        )

    def get_breadcrumbs(self):
        return [
            ("Members", reverse("members:list")),
            (self.object.user.display_name, None),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            businesses=scope_queryset(
                self.object.businesses.all(), self.request.user
            ).select_related("hub"),
            business_columns=(
                {"label": "Business", "field": "name"},
                {"label": "Type", "field": "business_type"},
                {"label": "Hub", "field": "hub__name"},
                {"label": "Status", "field": "status"},
            ),
            can_edit_member=self.request.user.has_perm(
                "members.change_memberprofile"
            ),
            can_add_business=self.request.user.has_perm("members.add_business"),
            row_edit_url_name="members:business_edit",
            can_edit_rows=self.request.user.has_perm("members.change_business"),
        )
        return context


class MemberUpdateView(ProtectedUpdateView):
    model = MemberProfile
    form_class = MemberProfileForm
    page_title = "Edit member"
    success_url_name = "members:list"
    cancel_url_name = "members:list"

    def get_queryset(self):
        return scope_queryset(MemberProfile.objects.all(), self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class MemberCreateView(ActiveHubInitialMixin, ProtectedCreateView):
    model = MemberProfile
    form_class = MemberProfileForm
    page_title = "Add member"
    success_url_name = "members:list"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class BusinessListView(ScopedModelListView):
    model = Business
    page_title = "Member Businesses"
    columns = (
        {"label": "Business", "field": "name"},
        {"label": "Member", "field": "member__user__display_name"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Type", "field": "business_type"},
        {"label": "Status", "field": "status"},
    )
    search_fields = ("name", "business_type", "registration_number")
    create_url_name = "members:business_create"
    create_label = "Add business"
    create_permission = "members.add_business"
    row_edit_url_name = "members:business_edit"
    row_edit_permission = "members.change_business"
    filter_hub = True


class BusinessCreateView(ActiveHubInitialMixin, ProtectedCreateView):
    model = Business
    form_class = BusinessForm
    page_title = "Add business"
    success_url_name = "members:businesses"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class BusinessUpdateView(ProtectedUpdateView):
    model = Business
    form_class = BusinessForm
    page_title = "Edit business"
    success_url_name = "members:businesses"
    cancel_url_name = "members:businesses"

    def get_queryset(self):
        return scope_queryset(Business.objects.all(), self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}
