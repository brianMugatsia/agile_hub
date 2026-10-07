const AUTO_DISMISS_MS = 6000;

function dismiss(toast) {
  toast.classList.add("is-leaving");
  setTimeout(() => toast.remove(), 220);
}

function bind(toast) {
  toast.querySelector("[data-toast-close]")?.addEventListener("click", () => dismiss(toast));
  // Errors stay until dismissed so they can't be missed.
  if (!toast.classList.contains("toast--danger")) {
    setTimeout(() => dismiss(toast), AUTO_DISMISS_MS);
  }
}

export function initToasts() {
  document.querySelectorAll("[data-toast]").forEach(bind);
}

/** showToast("Saved", "success") — builds nodes with textContent, so it is XSS-safe. */
export function showToast(message, type = "info") {
  const region = document.querySelector(".toast-region");
  if (!region) return;

  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.setAttribute("role", "status");
  toast.setAttribute("data-toast", "");

  const text = document.createElement("p");
  text.className = "toast__text";
  text.textContent = message;

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast__close";
  close.setAttribute("data-toast-close", "");
  close.setAttribute("aria-label", "Dismiss notification");
  close.textContent = "×";

  toast.append(text, close);
  region.append(toast);
  bind(toast);
}