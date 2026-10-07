import { initSidebar } from "./modules/sidebar.js";
import { initToasts } from "./modules/toast.js";
import { initFormValidation } from "./modules/form-validation.js";
import { initFormsets } from "./modules/formset.js";
import { initLoading } from "./modules/loading.js";
import { initModals } from "./modules/modal.js";
import { initMoney } from "./modules/money.js";
import { initTableFilters } from "./modules/table-filter.js";
import { initThemeToggle } from "./modules/theme-toggle.js";
import { initCommissionActions } from "./pages/commission-actions.js";
import { initDashboardCharts } from "./pages/dashboard-charts.js";
import { initFinanceForms } from "./pages/finance-forms.js";
import { initReports } from "./pages/reports.js";
import { initSalaryActions } from "./pages/salary-actions.js";
import { initSaleForm } from "./pages/sale-form.js";

function initDropdowns() {
  const open = () => document.querySelectorAll("details[data-dropdown][open]");

  document.addEventListener("click", (event) => {
    open().forEach((menu) => {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    open().forEach((menu) => {
      menu.removeAttribute("open");
      menu.querySelector("summary")?.focus();
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSidebar();
  initToasts();
  initDropdowns();
  initFormValidation();
  initFormsets();
  initLoading();
  initModals();
  initMoney();
  initTableFilters();
  initThemeToggle();
  initCommissionActions();
  initDashboardCharts();
  initFinanceForms();
  initReports();
  initSalaryActions();
  initSaleForm();
});