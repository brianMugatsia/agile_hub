export function initTableFilters() {
  document.querySelectorAll("[data-table-filter]").forEach((input) => {
    const table = document.getElementById(input.dataset.tableFilter);
    const rows = table?.querySelectorAll("tbody tr");
    if (!rows) return;
    input.addEventListener("input", () => {
      const query = input.value.trim().toLocaleLowerCase();
      rows.forEach((row) => {
        row.hidden = query !== "" && !row.textContent.toLocaleLowerCase().includes(query);
      });
    });
  });
}