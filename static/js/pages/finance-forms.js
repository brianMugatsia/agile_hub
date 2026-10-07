export function initFinanceForms() {
  document.querySelectorAll("[data-calculation-form]").forEach((form) => {
    const fields = form.querySelectorAll("[data-calculate]");
    const output = form.querySelector("[data-calculation-result]");
    if (!fields.length || !output) return;
    const update = () => {
      const values = [...fields].map((field) => Number(field.value));
      if (values.some((value) => !Number.isFinite(value))) {
        output.textContent = "";
        return;
      }
      const total = values.reduce((sum, value) => sum + value, 0);
      output.textContent = new Intl.NumberFormat(document.documentElement.lang || "en", {
        style: "currency",
        currency: form.dataset.currency || "KES",
      }).format(total);
    };
    fields.forEach((field) => field.addEventListener("input", update));
    update();
  });
}