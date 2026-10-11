const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Header turns to frosted white after scrolling; a thin bar shows reading progress. */
function initHeader() {
  const header = document.querySelector(".landing-header");
  const progress = document.querySelector(".landing-progress");
  if (!header) return;
  let ticking = false;
  const update = () => {
    ticking = false;
    const y = window.scrollY;
    header.classList.toggle("is-scrolled", y > 24);
    if (progress) {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      progress.style.setProperty("--p", max > 0 ? Math.min(y / max, 1).toFixed(4) : "0");
    }
  };
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  };
  update();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
}

/* Mobile menu button. */
function initMenu() {
  const header = document.querySelector(".landing-header");
  const button = document.querySelector("[data-landing-menu]");
  const nav = document.querySelector(".landing-nav");
  if (!header || !button || !nav) return;

  const setOpen = (open) => {
    header.classList.toggle("is-open", open);
    button.setAttribute("aria-expanded", String(open));
    button.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };
  button.addEventListener("click", () => setOpen(!header.classList.contains("is-open")));
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) setOpen(false);
  });
  document.addEventListener("click", (event) => {
    if (!header.contains(event.target)) setOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });
  window.matchMedia("(min-width: 901px)").addEventListener("change", (event) => {
    if (event.matches) setOpen(false);
  });
}

/* Highlights the nav link of the section that is currently on screen. */
function initScrollSpy() {
  if (!("IntersectionObserver" in window)) return;
  const links = [...document.querySelectorAll(".landing-nav a[href^='#']")];
  const sections = new Map();
  links.forEach((link) => {
    const section = document.querySelector(link.getAttribute("href"));
    if (section) sections.set(section, link);
  });
  if (!sections.size) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      links.forEach((link) => {
        link.classList.remove("is-current");
        link.removeAttribute("aria-current");
      });
      const active = sections.get(entry.target);
      active.classList.add("is-current");
      active.setAttribute("aria-current", "true");
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach((_, section) => observer.observe(section));
}

/* Gentle 3D tilt of the dashboard preview on desktop pointers. */
function initTilt() {
  const visual = document.querySelector(".landing-visual");
  if (!visual || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  visual.addEventListener("pointermove", (event) => {
    const bounds = visual.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;
    visual.style.setProperty("--tilt-x", `${(x * 8).toFixed(2)}deg`);
    visual.style.setProperty("--tilt-y", `${(y * -8).toFixed(2)}deg`);
  });
  visual.addEventListener("pointerleave", () => {
    visual.style.removeProperty("--tilt-x");
    visual.style.removeProperty("--tilt-y");
  });
}

/* Reveals elements as they scroll into view, staggering siblings. */
function initReveal() {
  const targets = document.querySelectorAll("[data-reveal]");
  if (!targets.length || !("IntersectionObserver" in window)) return;

  const counts = new Map();
  targets.forEach((target) => {
    const parent = target.parentElement;
    if (!parent || parent.tagName === "MAIN") return;
    const index = counts.get(parent) || 0;
    target.style.setProperty("--d", `${Math.min(index, 6) * 80}ms`);
    counts.set(parent, index + 1);
  });

  const observer = new IntersectionObserver((entries, current) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      current.unobserve(entry.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

  document.body.classList.add("motion-ready");
  targets.forEach((target) => observer.observe(target));
}

function init() {
  initHeader();
  initMenu();
  initScrollSpy();
  if (reduceMotion) return;
  initTilt();
  initReveal();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
  init();
}