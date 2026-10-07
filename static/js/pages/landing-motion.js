function initLandingMotion() {
  const targets = document.querySelectorAll("[data-reveal]");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!targets.length || motionPreference.matches || !("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries, currentObserver) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      currentObserver.unobserve(entry.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

  document.body.classList.add("motion-ready");
  targets.forEach((target) => observer.observe(target));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initLandingMotion, { once: true });
} else {
  initLandingMotion();
}
