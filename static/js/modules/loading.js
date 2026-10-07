export function initLoading() {
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) return;
      const button = form.querySelector('button[type="submit"], input[type="submit"]');
      if (!button || button.disabled) return;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.classList.add("is-loading");
      const label = button.querySelector("[data-loading-label]");
      if (label) label.textContent = button.dataset.loadingText || "Saving…";
      if (event.defaultPrevented) {
        button.disabled = false;
        button.removeAttribute("aria-busy");
      }
    });
  });
}