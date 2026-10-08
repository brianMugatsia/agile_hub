function initLandingMotion() {
  const targets = document.querySelectorAll("[data-reveal]");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (motionPreference.matches) return;

  const visual = document.querySelector(".landing-visual");
  const mock = visual?.querySelector(".mock");
  if (visual && mock && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    visual.addEventListener("pointermove", (event) => {
      const bounds = visual.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width - 0.5;
      const y = (event.clientY - bounds.top) / bounds.height - 0.5;
      visual.style.setProperty("--tilt-x", `${(x * 5).toFixed(2)}deg`);
      visual.style.setProperty("--tilt-y", `${(y * -5).toFixed(2)}deg`);
    });
    visual.addEventListener("pointerleave", () => {
      visual.style.removeProperty("--tilt-x");
      visual.style.removeProperty("--tilt-y");
    });
  }

  if (!targets.length || !("IntersectionObserver" in window)) return;

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
