from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.core.mixins import PageMixin
from apps.commissions.services import (
    approve_commission,
    pay_commission,
    reject_commission,
    reverse_commission,
)
from apps.core.generic import ScopedModelListView
from apps.core.exports import ScopedModelExportView
from apps.core.scoping import scope_queryset

from .forms import CommissionSettingForm
from .models import CommissionSetting, SalesAgentCommission


class CommissionListView(ScopedModelListView):
    model = SalesAgentCommission
    template_name = "commissions/commission_list.html"
    page_title = "Commissions"
    columns = (
        {"label": "Created", "field": "created_at"},
        {"label": "Agent", "field": "agent__display_name"},
        {"label": "Sale", "field": "sale__id"},
        {"label": "Rate", "field": "rate", "format": "percent"},
        {"label": "Amount", "field": "amount"},
        {"label": "Status", "field": "status"},
    )
    search_fields = (
        "agent__first_name",
        "agent__last_name",
        "agent__username",
        "agent__email",
        "sale__payment_reference",
        "sale__customer_name",
        "sale__customer_phone",
    )
    date_filter_field = "created_at"
    filter_fields = (("status", SalesAgentCommission.Status.choices),)
    export_url_name = "commissions:export"

    def get_queryset(self):
        return super().get_queryset().select_related("agent", "sale")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_view_commission_settings"] = self.request.user.has_perm(
            "commissions.view_commissionsetting"
        )
        context["can_approve_commissions"] = self.request.user.has_perm(
            "commissions.approve_salesagentcommission"
        )
        return context


class PendingCommissionListView(CommissionListView):
    template_name = "commissions/pending_commissions.html"
    page_title = "Pending commissions"
    filter_fields = ()

    def get_queryset(self):
        return super().get_queryset().filter(status=SalesAgentCommission.Status.PENDING)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        query["status"] = SalesAgentCommission.Status.PENDING
        context["export_query"] = query.urlencode()
        return context


class CommissionExportView(ScopedModelExportView):
    list_view_class = CommissionListView


class CommissionDetailView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, DetailView):
    model = SalesAgentCommission
    template_name = "commissions/commission_detail.html"
    context_object_name = "commission"
    permission_required = "commissions.view_salesagentcommission"
    page_title = "Commission details"

    def get_queryset(self):
        return scope_queryset(
            SalesAgentCommission.objects.select_related(
                "agent", "sale", "sale__hub", "approved_by", "paid_by"
            ),
            self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_approve"] = self.request.user.has_perm(
            "commissions.approve_salesagentcommission"
        )
        context["can_reject"] = self.request.user.has_perm(
            "commissions.reject_salesagentcommission"
        )
        context["can_pay"] = self.request.user.has_perm(
            "commissions.pay_salesagentcommission"
        )
        context["can_reverse"] = self.request.user.has_perm(
            "commissions.reverse_salesagentcommission"
        )
        return context


class AgentCommissionStatementView(
    LoginRequiredMixin, PermissionRequiredMixin, PageMixin, TemplateView
):
    template_name = "commissions/agent_statement.html"
    permission_required = "commissions.view_salesagentcommission"
    page_title = "Agent commission statement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = get_object_or_404(
            User.objects.filter(role=Role.SALES_AGENT),
            pk=self.kwargs["agent_id"],
        )
        commissions = scope_queryset(
            SalesAgentCommission.objects.select_related("sale", "sale__hub", "agent"),
            self.request.user,
        ).filter(agent=agent)
        if self.request.user.role == Role.SALES_AGENT and agent.pk != self.request.user.pk:
            raise PermissionDenied
        if self.request.user.role not in (Role.SUPER_ADMIN, Role.ADMIN, Role.SALES_AGENT):
            if not commissions.exists():
                raise PermissionDenied
        totals = commissions.aggregate(
            earned=Sum(
                "amount",
                filter=Q(
                    status__in=[
                        SalesAgentCommission.Status.PENDING,
                        SalesAgentCommission.Status.APPROVED,
                        SalesAgentCommission.Status.PAID,
                    ]
                ),
            ),
            paid=Sum("amount", filter=Q(status=SalesAgentCommission.Status.PAID)),
            pending=Sum("amount", filter=Q(status=SalesAgentCommission.Status.PENDING)),
        )
        context.update(
            agent=agent,
            commissions=commissions,
            earned_total=totals["earned"] or 0,
            paid_total=totals["paid"] or 0,
            pending_total=totals["pending"] or 0,
            columns=(
                {"label": "Created", "field": "created_at"},
                {"label": "Sale", "field": "sale__id"},
                {"label": "Hub", "field": "sale__hub__name"},
                {"label": "Rate", "field": "rate", "format": "percent"},
                {"label": "Amount", "field": "amount"},
                {"label": "Status", "field": "status"},
            ),
        )
        return context


class CommissionSettingsView(LoginRequiredMixin, PermissionRequiredMixin, PageMixin, FormView):
    template_name = "commissions/commission_settings.html"
    form_class = CommissionSettingForm
    permission_required = "commissions.view_commissionsetting"
    page_title = "Commission settings"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["settings"] = CommissionSetting.objects.all()
        if not self.request.user.has_perm("commissions.add_commissionsetting"):
            context.pop("form", None)
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("commissions.add_commissionsetting"):
            raise PermissionDenied
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        setting = form.save(commit=False)
        setting.created_by = self.request.user
        setting.save()
        messages.success(self.request, "Commission rate saved.")
        return redirect("commissions:settings")


class CommissionActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    service = None
    permission_required = ""
    success_message = "Commission updated."
    reason_required = False

    def post(self, request, pk):
        kwargs = {"commission_id": pk, "actor": request.user}
        if self.reason_required:
            kwargs["reason"] = request.POST.get("reason", "")
        try:
            self.service(**kwargs)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, self.success_message)
        return redirect("commissions:list")


class ApproveCommissionView(CommissionActionView):
    service = staticmethod(approve_commission)
    permission_required = "commissions.approve_salesagentcommission"
    success_message = "Commission approved."


class RejectCommissionView(CommissionActionView):
    service = staticmethod(reject_commission)
    permission_required = "commissions.reject_salesagentcommission"
    success_message = "Commission rejected."
    reason_required = True


class PayCommissionView(CommissionActionView):
    service = staticmethod(pay_commission)
    permission_required = "commissions.pay_salesagentcommission"
    success_message = "Commission marked as paid."


class ReverseCommissionView(CommissionActionView):
    service = staticmethod(reverse_commission)
    permission_required = "commissions.reverse_salesagentcommission"
    success_message = "Commission reversed."
    reason_required = True