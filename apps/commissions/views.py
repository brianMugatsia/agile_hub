from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect
from django.views import View

from apps.commissions.services import (
    approve_commission,
    pay_commission,
    reject_commission,
    reverse_commission,
)
from apps.core.generic import ScopedModelListView

from .models import SalesAgentCommission


class CommissionListView(ScopedModelListView):
    model = SalesAgentCommission
    template_name = "commissions/commission_list.html"
    page_title = "Commissions"
    columns = ()
    search_fields = ("agent__first_name", "agent__last_name", "sale__payment_reference")


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