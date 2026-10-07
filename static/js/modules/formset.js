function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function initFormsets() {
  document.querySelectorAll("[data-formset]").forEach((container) => {
    const prefix = container.dataset.formset;
    const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
    const addButton = container.querySelector("[data-formset-add]");
    const template = container.querySelector("template[data-formset-template]");
    if (!total || !addButton || !template) return;

    addButton.addEventListener("click", () => {
      const index = Number.parseInt(total.value, 10);
      if (!Number.isInteger(index)) return;
      const fragment = template.content.cloneNode(true);
      const pattern = new RegExp(escapeRegExp(`${prefix}-__prefix__`), "g");
      fragment.querySelectorAll("[name], [id], label[for]").forEach((element) => {
        for (const attribute of ["name", "id", "for"]) {
          const value = element.getAttribute(attribute);
          if (value) element.setAttribute(attribute, value.replace(pattern, `${prefix}-${index}`));
        }
      });
      container.insertBefore(fragment, addButton);
      total.value = String(index + 1);
    });

    container.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-formset-remove]");
      if (!removeButton || !container.contains(removeButton)) return;
      const row = removeButton.closest("[data-formset-row]");
      const deleted = row?.querySelector('input[name$="-DELETE"]');
      if (deleted) {
        deleted.checked = true;
        row.hidden = true;
      } else {
        row?.remove();
      }
    });
  });
}