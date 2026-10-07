from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView


class ReportIndexView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "reports/index.html"
    permission_required = "accounts.export_reports"
    page_title = "Reports"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["report_links"] = [
            ("Sales", "sales:list"),
            ("Inventory", "inventory:list"),
            ("Commissions", "commissions:list"),
            ("Payroll", "payroll:salary_list"),
            ("Cash flow", "finance:cash_flow"),
            ("Audit trail", "audit:list"),
        ]
        return context