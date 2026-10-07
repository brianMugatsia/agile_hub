export function initFormValidation() {
  document.querySelectorAll("form[data-validate]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (form.checkValidity()) return;
      event.preventDefault();
      form.classList.add("was-validated");
      form.querySelector(":invalid")?.focus();
    });
  });

  document.querySelectorAll("input[required], select[required], textarea[required]").forEach((field) => {
    field.addEventListener("input", () => {
      field.setAttribute("aria-invalid", String(!field.validity.valid));
    });
  });
}