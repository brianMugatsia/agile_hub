from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.commissions.models import ServiceCommission
from apps.core.generic import ProtectedCreateView, ProtectedUpdateView, ScopedModelListView
from apps.core.mixins import ActiveHubInitialMixin, PageMixin
from apps.core.scoping import scope_queryset
from apps.services.models import ServiceProvider, ServiceProviderStatus, ServiceBooking

from .forms import MemberProfileForm, MemberCreateForm, CustomerForm, BusinessForm
from .models import MemberProfile, Business


def _provider_stats():
    return {
        "total_providers_count": ServiceProvider.objects.count(),
        "active_sales_agents_count": User.objects.filter(role=Role.SALES_AGENT, is_active=True).count() + MemberProfile.objects.filter(user__role=Role.MEMBER, customer_type=MemberProfile.CustomerType.FARMER).count(),
        "dormant_providers_count": ServiceProvider.objects.filter(status=ServiceProviderStatus.DORMANT).count(),
        "active_providers_count": ServiceProvider.objects.filter(status=ServiceProviderStatus.ACTIVE).count(),
        "suspended_providers_count": ServiceProvider.objects.filter(status=ServiceProviderStatus.SUSPENDED).count(),
    }


class MemberListView(ScopedModelListView):
    model = MemberProfile
    page_title = "Members & Farmers"
    template_name = "members/member_list.html"
    columns = (
        {"label": "Name", "field": "display_name"},
        {"label": "Phone Number", "field": "phone_number"},
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "name", "phone_number", "crops", "location")
    create_url_name = "members:create"
    create_label = "Add member"
    create_permission = "members.add_memberprofile"
    import_url_name = "members:import"
    import_permission = "members.add_memberprofile"
    row_edit_url_name = "members:edit"
    row_edit_permission = "members.change_memberprofile"
    filter_hub = False

    def get_queryset(self):
        return super().get_queryset().filter(customer_type=MemberProfile.CustomerType.FARMER)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_provider_stats())
        context["active_tab"] = "all_members"
        return context


class CustomerListView(ScopedModelListView):
    model = MemberProfile
    page_title = "Clients & Customers"
    template_name = "members/customer_list.html"
    columns = (
        {"label": "Name", "field": "display_name"},
        {"label": "Category", "field": "customer_type_display"},
        {"label": "ID / National ID", "field": "national_id"},
        {"label": "Phone", "field": "phone_number"},
        {"label": "Location", "field": "location"},
        {"label": "Crops", "field": "crops"},
        {"label": "Hub", "field": "hub__name"},
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "name", "phone_number", "national_id", "crops", "location")
    create_url_name = "members:customer_create"
    create_label = "Add customer"
    create_permission = "members.add_memberprofile"
    row_detail_url_name = "members:customer_detail"
    row_edit_url_name = "members:customer_edit"
    row_edit_permission = "members.change_memberprofile"
    filter_hub = False

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.GET.get("category", "")
        if category == "lead":
            queryset = queryset.filter(customer_type=MemberProfile.CustomerType.LEAD)
        elif category == "farmer":
            queryset = queryset.filter(customer_type=MemberProfile.CustomerType.FARMER)
        elif category == "organization":
            queryset = queryset.filter(customer_type=MemberProfile.CustomerType.ORGANIZATION)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scoped = scope_queryset(MemberProfile.objects.all(), self.request.user)
        context.update(
            total_customers_count=scoped.count(),
            leads_count=scoped.filter(customer_type=MemberProfile.CustomerType.LEAD).count(),
            farmers_count=scoped.filter(customer_type=MemberProfile.CustomerType.FARMER).count(),
            organizations_count=scoped.filter(customer_type=MemberProfile.CustomerType.ORGANIZATION).count(),
            current_category=self.request.GET.get("category", ""),
        )
        return context


class CustomerCreateView(ActiveHubInitialMixin, ProtectedCreateView):
    model = MemberProfile
    form_class = CustomerForm
    page_title = "Add customer or lead"
    success_url_name = "members:customers_list"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class CustomerUpdateView(ProtectedUpdateView):
    model = MemberProfile
    form_class = CustomerForm
    page_title = "Edit customer or lead"
    success_url_name = "members:customers_list"
    cancel_url_name = "members:customers_list"

    def get_queryset(self):
        return scope_queryset(MemberProfile.objects.all(), self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class CustomerUpgradeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "members.change_memberprofile"

    def post(self, request, pk):
        profile = get_object_or_404(
            scope_queryset(MemberProfile.objects.all(), request.user),
            pk=pk
        )
        profile.customer_type = MemberProfile.CustomerType.FARMER
        profile.save()
        return redirect("members:customer_detail", pk=pk)


class CustomerDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = MemberProfile
    template_name = "members/customer_detail.html"
    context_object_name = "customer"
    permission_required = "members.view_memberprofile"
    page_title = "Customer Profile"

    def get_queryset(self):
        return scope_queryset(
            MemberProfile.objects.select_related("user", "hub").prefetch_related("services"),
            self.request.user,
        )

    def get_breadcrumbs(self):
        return [
            ("Clients & Customers", reverse("members:customers_list")),
            (self.object.display_name, None),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            assigned_services=self.object.services.all(),
            can_edit_customer=self.request.user.has_perm("members.change_memberprofile"),
        )
        return context


class MemberSalesAgentsListView(ScopedModelListView):
    model = MemberProfile
    page_title = "Members Who Are Sales Agents"
    template_name = "members/member_list.html"
    columns = (
        {"label": "Name", "field": "display_name"},
        {"label": "Phone Number", "field": "phone_number"},
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone_number")
    create_url_name = "members:create"
    create_label = "Add member"
    create_permission = "members.add_memberprofile"
    filter_hub = False

    def get_queryset(self):
        return super().get_queryset().filter(Q(user__role=Role.SALES_AGENT) | Q(user__role=Role.MEMBER)).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_provider_stats())
        context["active_tab"] = "sales_agents"
        return context


class MemberServiceProvidersListView(ScopedModelListView):
    model = MemberProfile
    page_title = "Members Who Are Service Providers"
    template_name = "members/member_list.html"
    columns = (
        {"label": "Name", "field": "display_name"},
        {"label": "Phone Number", "field": "phone_number"},
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone_number")
    create_url_name = "members:create"
    create_label = "Add member"
    create_permission = "members.add_memberprofile"
    filter_hub = False

    def get_queryset(self):
        return super().get_queryset().filter(service_providers__isnull=False).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_provider_stats())
        context["active_tab"] = "service_providers"
        return context


class MemberDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = MemberProfile
    template_name = "members/member_detail.html"
    context_object_name = "member"
    permission_required = "members.view_memberprofile"
    page_title = "Member & Customer details"

    def get_queryset(self):
        return scope_queryset(
            MemberProfile.objects.select_related("user", "hub"),
            self.request.user,
        )

    def get_breadcrumbs(self):
        return [
            ("Clients & Customers", reverse("members:customers_list")),     
            (self.object.display_name, None),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object.user

        commissions = ServiceCommission.objects.filter(
            Q(provider__member=self.object) | Q(provider__in=self.object.service_providers.all())
        ).select_related("provider", "booking", "service_type").distinct()

        sales_commissions = []
        sales_records = []
        if user:
            from apps.commissions.models import SalesAgentCommission
            from apps.sales.models import Sale
            sales_commissions = SalesAgentCommission.objects.filter(agent=user).select_related("sale__hub").order_by("-created_at")
            sales_records = Sale.objects.filter(agent=user).select_related("hub").order_by("-completed_at")[:20]

        bookings = scope_queryset(
            ServiceBooking.objects.filter(
                Q(member=self.object) | Q(service_provider__member=self.object) | Q(service_provider__in=self.object.service_providers.all())
            ).distinct(),
            self.request.user
        ).select_related("service_type", "resource")

        contributions = scope_queryset(
            self.object.businesses.all(), self.request.user
        ).select_related("hub")

        total_commissions = commissions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_sales_commissions = sum((c.amount for c in sales_commissions), Decimal("0.00"))
        total_contributions = contributions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_bookings_amount = bookings.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

        context.update(
            contributions=contributions,
            contribution_columns=(
                {"label": "Contribution", "field": "name"},
                {"label": "Type", "field": "business_type"},
                {"label": "Hub", "field": "hub__name"},
                {"label": "Amount", "field": "amount"},
                {"label": "Payment Status", "field": "payment_status_display"},
                {"label": "Status", "field": "status"},
            ),
            assigned_services=self.object.services.all(),
            service_providers=self.object.service_providers.all(),
            service_commissions=commissions,
            sales_commissions=sales_commissions[:20],
            sales_records=sales_records,
            service_bookings=bookings,
            reports_summary={
                "total_commissions": total_commissions,
                "total_sales_commissions": total_sales_commissions,
                "total_contributions": total_contributions,
                "total_bookings_amount": total_bookings_amount,
                "bookings_count": bookings.count(),
                "commissions_count": commissions.count() + len(sales_commissions),
            },
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
        {"label": "Member Name", "field": "member__display_name"},
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
    filter_fields = (
        ("is_paid", (("True", "Paid"), ("False", "Not Paid"))),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        is_paid = self.request.GET.get("is_paid", "")
        if is_paid == "True":
            queryset = queryset.filter(is_paid=True)
        elif is_paid == "False":
            queryset = queryset.filter(is_paid=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        scoped_members = scope_queryset(MemberProfile.objects.all(), self.request.user)
        total_members_count = scoped_members.count()

        equal_unit_amount = Decimal("10000.00")
        total_expected_amount = total_members_count * equal_unit_amount

        scoped_businesses = scope_queryset(Business.objects.all(), self.request.user)
        paid_businesses = scoped_businesses.filter(is_paid=True)

        total_collected_amount = paid_businesses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        paid_member_ids = paid_businesses.values_list("member_id", flat=True).distinct()
        members_paid_count = scoped_members.filter(pk__in=paid_member_ids).count()
        members_unpaid_count = max(0, total_members_count - members_paid_count)

        total_unpaid_amount = members_unpaid_count * equal_unit_amount

        context.update(
            total_contributions_count=scoped_businesses.count(),
            total_expected_amount=total_expected_amount,
            total_collected_amount=total_collected_amount,
            total_unpaid_amount=total_unpaid_amount,
            members_paid_count=members_paid_count,
            members_unpaid_count=members_unpaid_count,
            total_contribution_amount=total_collected_amount,
            total_members_count=total_members_count,
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
