import { initSidebar } from "./modules/sidebar.js";
import { initToasts } from "./modules/toast.js";
import { initFormValidation } from "./modules/form-validation.js";
import { initFormsets } from "./modules/formset.js";
import { initLoading } from "./modules/loading.js";
import { initModals } from "./modules/modal.js";
import { initMoney } from "./modules/money.js";
import { initMotion } from "./modules/motion.js";
import { initTableFilters } from "./modules/table-filter.js";
import { initThemeToggle } from "./modules/theme-toggle.js";
import { initCommissionActions } from "./pages/commission-actions.js";
import { initDashboardCharts } from "./pages/dashboard-charts.js";
import { initFinanceForms } from "./pages/finance-forms.js";
import { initReports } from "./pages/reports.js";
import { initSalaryActions } from "./pages/salary-actions.js";
import { initSaleForm } from "./pages/sale-form.js";

function initDropdowns() {
  const menus = [...document.querySelectorAll("details[data-dropdown]")];
  const close = (menu, restoreFocus = false) => {
    if (!menu.open) return;
    menu.open = false;
    if (restoreFocus) menu.querySelector("summary")?.focus();
  };

  menus.forEach((menu) => {
    const trigger = menu.querySelector("summary");
    if (!trigger) return;
    trigger.setAttribute("aria-expanded", String(menu.open));
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      menu.open = !menu.open;
      trigger.setAttribute("aria-expanded", String(menu.open));
    });
    menu.addEventListener("toggle", () => {
      trigger.setAttribute("aria-expanded", String(menu.open));
    });
  });

  document.addEventListener("click", (event) => {
    menus.forEach((menu) => {
      if (!menu.contains(event.target)) close(menu);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    menus.forEach((menu) => close(menu, true));
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
  initMotion();
  initTableFilters();
  initThemeToggle();
  initCommissionActions();
  initDashboardCharts();
  initFinanceForms();
  initReports();
  initSalaryActions();
  initSaleForm();
});