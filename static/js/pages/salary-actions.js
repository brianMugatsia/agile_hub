export function initSalaryActions() {
  document.querySelectorAll("form[data-confirm-action='salary']").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirmMessage || "Continue with this salary action?")) {
        event.preventDefault();
      }
    });
  });
}