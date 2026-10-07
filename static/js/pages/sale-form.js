import { formatMoney } from "../modules/money.js";

export function initSaleForm() {
  document.querySelectorAll("[data-sale-form]").forEach((form) => {
    const product = form.querySelector("[data-sale-price]");
    const quantity = form.querySelector("[data-sale-quantity]");
    const total = form.querySelector("[data-sale-total]");
    if (!product || !quantity || !total) return;

    const updateTotal = () => {
      const option = product.selectedOptions[0];
      const price = Number(option?.dataset.price);
      const count = Number(quantity.value);
      if (!Number.isFinite(price) || !Number.isFinite(count) || count < 1) {
        total.textContent = "";
        return;
      }
      total.textContent = formatMoney(price * count, form.dataset.currency || "KES");
    };

    product.addEventListener("change", updateTotal);
    quantity.addEventListener("input", updateTotal);
    updateTotal();
  });
}