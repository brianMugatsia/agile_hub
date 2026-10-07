export function initSidebar() {
  const shell = document.querySelector(".app-shell");
  if (!shell) return;

  const toggle = document.querySelector("[data-sidebar-toggle]");
  const sidebar = shell.querySelector(".sidebar");
  if (!sidebar || !toggle) return;
  const closeButton = sidebar.querySelector("[data-sidebar-close]");
  const mobileQuery = window.matchMedia("(max-width: 1023px)");
  const focusable = () => sidebar.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );

  const setOpen = (isOpen) => {
    const open = mobileQuery.matches && isOpen;
    shell.dataset.sidebarState = open ? "open" : "closed";
    toggle.setAttribute("aria-expanded", String(open));
    sidebar.setAttribute("aria-hidden", String(mobileQuery.matches && !open));
    sidebar.inert = mobileQuery.matches && !open;
    document.body.classList.toggle("is-locked", open);
    return open;
  };

  toggle.addEventListener("click", () => {
    if (setOpen(shell.dataset.sidebarState !== "open")) closeButton?.focus();
  });

  document.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-sidebar-close]")) {
      setOpen(false);
      toggle.focus();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && shell.dataset.sidebarState === "open") {
      setOpen(false);
      toggle.focus();
      return;
    }
    if (event.key !== "Tab" || shell.dataset.sidebarState !== "open") return;
    const items = [...focusable()];
    if (!items.length) {
      event.preventDefault();
      closeButton?.focus();
      return;
    }
    if (event.shiftKey && document.activeElement === items[0]) {
      event.preventDefault();
      items.at(-1).focus();
    } else if (!event.shiftKey && document.activeElement === items.at(-1)) {
      event.preventDefault();
      items[0].focus();
    }
  });

  const onViewportChange = () => setOpen(false);
  if (typeof mobileQuery.addEventListener === "function") {
    mobileQuery.addEventListener("change", onViewportChange);
  } else {
    mobileQuery.addListener(onViewportChange);
  }
  setOpen(false);
}