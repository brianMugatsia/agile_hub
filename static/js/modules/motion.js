const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Adds a soft shadow to the top bar once the page has been scrolled. */
function initTopbarShadow() {
  const topbar = document.querySelector(".topbar");
  if (!topbar) return;
  const update = () => topbar.classList.toggle("is-scrolled", window.scrollY > 4);
  update();
  window.addEventListener("scroll", update, { passive: true });
}

/* Numbers table rows so the CSS can stagger their entrance (dashboard has its own motion). */
function initRowStagger() {
  document.querySelectorAll(".app-shell .page > .card tbody").forEach((tbody) => {
    Array.from(tbody.rows).forEach((row, index) => row.style.setProperty("--r", Math.min(index, 14)));
  });
}

/* Material-style ripple on buttons inside the app. */
function initRipple() {
  document.addEventListener("pointerdown", (event) => {
    const button = event.target.closest(".app-shell .btn");
    if (!button || button.disabled || button.classList.contains("is-disabled")) return;
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const ripple = document.createElement("span");
    ripple.className = "btn__ripple";
    ripple.style.width = `${size}px`;
    ripple.style.height = `${size}px`;
    ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
    ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
    button.append(ripple);
    ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
  });
}

/* Fades the page slightly while moving to another page or switching hub. */
function initPageLeave() {
  const page = document.querySelector(".app-shell .page");
  if (!page) return;
  const leave = () => {
    page.classList.add("is-leaving");
    window.setTimeout(() => page.classList.remove("is-leaving"), 4000);
  };
  window.addEventListener("pageshow", () => page.classList.remove("is-leaving"));

  document.querySelector("#active-hub")?.addEventListener("change", leave);

  document.querySelectorAll(".sidebar__link").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (link.target === "_blank" || link.origin !== window.location.origin) return;
      if (link.pathname === window.location.pathname && link.search === window.location.search) return;
      leave();
    });
  });
}

export function initMotion() {
  initTopbarShadow();
  initRowStagger();
  if (REDUCE_MOTION) return;
  initRipple();
  initPageLeave();
}