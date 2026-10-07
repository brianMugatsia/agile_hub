export function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content ?? "";
}

export function csrfHeaders(extra = {}) {
  return { "X-CSRFToken": getCsrfToken(), ...extra };
}