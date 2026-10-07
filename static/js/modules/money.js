const formatters = new Map();

function formatter(currency) {
  if (!formatters.has(currency)) {
    formatters.set(currency, new Intl.NumberFormat(document.documentElement.lang || "en", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }));
  }
  return formatters.get(currency);
}

export function formatMoney(amount, currency = "KES") {
  const value = Number(amount);
  if (!Number.isFinite(value)) return "";
  return formatter(currency).format(value);
}

export function initMoney() {
  document.querySelectorAll("[data-money]").forEach((element) => {
    const currency = element.dataset.currency || document.body.dataset.currency || "KES";
    element.textContent = formatMoney(element.dataset.money, currency);
  });
}