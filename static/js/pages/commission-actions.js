export function initCommissionActions() {
  document.querySelectorAll("form[data-confirm-action='commission']").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirmMessage || "Continue with this commission action?")) {
        event.preventDefault();
      }
    });
  });
}