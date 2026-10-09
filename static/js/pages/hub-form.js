(() => {
  const preview = document.querySelector("[data-hub-preview]");
  if (!preview) return;

  const fields = {
    code: document.getElementById("id_code"),
    name: document.getElementById("id_name"),
    region: document.getElementById("id_region"),
    address: document.getElementById("id_address"),
    phone: document.getElementById("id_phone_number"),
    manager: document.getElementById("id_manager"),
    status: document.getElementById("id_status"),
  };
  const placeholders = {
    code: "CODE",
    name: "Hub name",
    region: "Region",
    address: "Address",
    phone: "Phone",
    manager: "No manager assigned",
    status: "Active",
  };
  const avatar = preview.querySelector("[data-preview-avatar]");

  const read = (key) => {
    const el = fields[key];
    if (!el) return "";
    if (el.tagName === "SELECT") {
      const option = el.options[el.selectedIndex];
      return option && option.value ? option.textContent.trim() : "";
    }
    return el.value.trim();
  };

  const render = () => {
    preview.querySelectorAll("[data-preview]").forEach((node) => {
      const key = node.dataset.preview;
      const value = read(key);
      node.textContent = value || placeholders[key];
      node.classList.toggle("is-placeholder", !value);
    });
    const statusValue = fields.status ? fields.status.value : "";
    preview.dataset.status = (statusValue || "ACTIVE").toLowerCase();
    const manager = read("manager");
    if (avatar) avatar.textContent = manager ? manager.charAt(0).toUpperCase() : "?";
  };

  Object.values(fields).forEach((el) => {
    if (!el) return;
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  });
  render();
})();