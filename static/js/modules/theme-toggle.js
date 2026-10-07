const preferenceKey = "boost-hub-theme";

export function initThemeToggle() {
  const root = document.documentElement;
  let saved = null;
  try {
    saved = window.localStorage.getItem(preferenceKey);
  } catch (error) {
    if (!(error instanceof DOMException)) throw error;
  }
  if (saved === "dark" || saved === "light") root.dataset.theme = saved;

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    const sync = () => {
      const isDark = root.dataset.theme === "dark";
      button.setAttribute("aria-pressed", String(isDark));
      button.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    };
    sync();
    button.addEventListener("click", () => {
      const theme = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = theme;
      try {
        window.localStorage.setItem(preferenceKey, theme);
      } catch (error) {
        if (!(error instanceof DOMException)) throw error;
      }
      sync();
    });
  });
}