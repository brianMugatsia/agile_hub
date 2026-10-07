export function initReports() {
  document.querySelectorAll("[data-report-print]").forEach((button) => {
    button.addEventListener("click", () => window.print());
  });
}