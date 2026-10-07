export function initDashboardCharts() {
  document.querySelectorAll("[data-chart-value]").forEach((element) => {
    const value = Number(element.dataset.chartValue);
    if (Number.isFinite(value)) element.style.setProperty("--chart-value", String(Math.max(0, Math.min(100, value))));
  });
}