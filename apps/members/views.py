from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.urls import reverse
from django.views.generic import DetailView

from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView
from apps.core.mixins import ActiveHubInitialMixin, PageMixin
from apps.core.scoping import scope_queryset

from .forms import MemberProfileForm, MemberCreateForm, BusinessForm
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
    import_url_name = "members:import"
    import_permission = "members.add_memberprofile"
    row_edit_url_name = "members:edit"
    row_edit_permission = "members.change_memberprofile"
    filter_hub = False


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
            contributions=scope_queryset(
                self.object.businesses.all(), self.request.user
            ).select_related("hub"),
            contribution_columns=(
                {"label": "Contribution", "field": "name"},
                {"label": "Type", "field": "business_type"},
                {"label": "Hub", "field": "hub__name"},
                {"label": "Status", "field": "status"},
            ),
            can_edit_member=self.request.user.has_perm(
                "members.change_memberprofile"
            ),
            can_add_contribution=self.request.user.has_perm("members.add_business"),
            row_edit_url_name="members:contribution_edit",
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
    form_class = MemberCreateForm
    page_title = "Add member"
    success_url_name = "members:list"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class ContributionListView(ScopedModelListView):
    model = Business
    page_title = "Member Contributions"
    template_name = "members/contribution_list.html"
    columns = (
        {"label": "Contribution Name", "field": "name"},
        {"label": "Member Name", "field": "member__user__display_name"},
        {"label": "Amount", "field": "amount"},
        {"label": "Payment Status", "field": "payment_status_display"},
    )
    search_fields = ("name", "business_type", "registration_number")
    create_url_name = "members:contribution_create"
    create_label = "Add contribution"
    create_permission = "members.add_business"
    import_url_name = "members:contribution_import"
    import_permission = "members.add_business"
    row_edit_url_name = "members:contribution_edit"
    row_edit_permission = "members.change_business"
    filter_hub = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        total_contributions_count = queryset.count()
        equal_unit_amount = Decimal("10000.00")
        total_expected_amount = total_contributions_count * equal_unit_amount
        
        paid_qs = queryset.filter(amount__gt=0)
        unpaid_qs = queryset.filter(Q(amount__isnull=True) | Q(amount=0))
        
        total_collected_amount = paid_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_unpaid_amount = unpaid_qs.count() * equal_unit_amount
        
        members_paid_count = paid_qs.count()
        members_unpaid_count = unpaid_qs.count()

        context.update(
            total_contributions_count=total_contributions_count,
            total_expected_amount=total_expected_amount,
            total_collected_amount=total_collected_amount,
            total_unpaid_amount=total_unpaid_amount,
            members_paid_count=members_paid_count,
            members_unpaid_count=members_unpaid_count,
            total_contribution_amount=total_collected_amount,
        )
        return context


class ContributionCreateView(ActiveHubInitialMixin, ProtectedCreateView):
    model = Business
    form_class = BusinessForm
    page_title = "Add contribution"
    success_url_name = "members:contributions"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class ContributionUpdateView(ProtectedUpdateView):
    model = Business
    form_class = BusinessForm
    page_title = "Edit contribution"
    success_url_name = "members:contributions"
    cancel_url_name = "members:contributions"

    def get_queryset(self):
        return scope_queryset(Business.objects.all(), self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}
