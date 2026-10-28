export function initSearchableSelects() {
  document.querySelectorAll("select[data-searchable-select]").forEach((select) => {
    if (select.dataset.searchEnhanced) return;
    select.dataset.searchEnhanced = "true";

    // Hide original select
    select.style.display = "none";

    // Create wrapper
    const wrapper = document.createElement("div");
    wrapper.className = "searchable-select-wrapper";
    wrapper.style.position = "relative";

    // Create search input
    const input = document.createElement("input");
    input.type = "text";
    input.className = "input";
    input.placeholder = "Search or select...";
    input.autocomplete = "off";

    // Set initial text if an option is selected
    const selectedOption = select.options[select.selectedIndex];
    if (selectedOption && selectedOption.value) {
      input.value = selectedOption.textContent.trim();
    }

    // Create dropdown container
    const dropdown = document.createElement("div");
    dropdown.className = "searchable-select-dropdown";
    dropdown.style.cssText = "position: absolute; top: 100%; left: 0; right: 0; max-height: 220px; overflow-y: auto; background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.1); z-index: 1000; display: none; margin-top: 4px;";

    const renderOptions = (filter = "") => {
      dropdown.innerHTML = "";
      const query = filter.trim().toLowerCase();
      let matchCount = 0;

      Array.from(select.options).forEach((opt) => {
        if (!opt.value) return; // skip empty/placeholder option
        const text = opt.textContent.trim();
        if (query === "" || text.toLowerCase().includes(query)) {
          matchCount++;
          const item = document.createElement("div");
          item.className = "searchable-select-item";
          item.style.cssText = "padding: 10px 14px; cursor: pointer; font-size: 0.875rem; color: #1e293b; border-bottom: 1px solid #f1f5f9;";
          item.textContent = text;
          item.addEventListener("mouseenter", () => item.style.background = "#f8fafc");
          item.addEventListener("mouseleave", () => item.style.background = "#fff");
          item.addEventListener("click", () => {
            select.value = opt.value;
            input.value = text;
            dropdown.style.display = "none";
            select.dispatchEvent(new Event("change"));
          });
          dropdown.appendChild(item);
        }
      });

      if (matchCount === 0) {
        const noMatch = document.createElement("div");
        noMatch.style.cssText = "padding: 10px 14px; font-size: 0.875rem; color: #94a3b8;";
        noMatch.textContent = "No matching options found";
        dropdown.appendChild(noMatch);
      }
    };

    input.addEventListener("focus", () => {
      renderOptions();
      dropdown.style.display = "block";
    });

    input.addEventListener("input", () => {
      renderOptions(input.value);
      dropdown.style.display = "block";
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
      if (!wrapper.contains(e.target)) {
        dropdown.style.display = "none";
      }
    });

    wrapper.appendChild(input);
    wrapper.appendChild(dropdown);
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
  });
}
