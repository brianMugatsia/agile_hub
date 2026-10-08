(() => {
  const root = document.querySelector(".dash");
  if (!root) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Time-aware greeting (pure enhancement) */
  const greeting = root.querySelector("[data-greeting]");
  if (greeting) {
    const h = new Date().getHours();
    greeting.textContent = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }

  /* Cursor spotlight on cards */
  root.querySelectorAll("[data-spot]").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    });
  });

  if (reduceMotion || !("IntersectionObserver" in window)) return;

  /* Count-up for numeric stat values, keeping prefix/suffix (e.g. "KES 128,400") */
  const countUp = (el) => {
    if (el.children.length) return;
    const text = el.textContent.trim();
    const match = text.match(/-?\d[\d,]*(?:\.\d+)?/);
    if (!match) return;

    const raw = match[0];
    const target = parseFloat(raw.replace(/,/g, ""));
    if (!Number.isFinite(target)) return;

    const decimals = (raw.split(".")[1] || "").length;
    const useCommas = raw.includes(",");
    const prefix = text.slice(0, match.index);
    const suffix = text.slice(match.index + raw.length);
    const format = (n) =>
      useCommas
        ? n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
        : n.toFixed(decimals);

    const duration = 1200;
    let start = null;
    el.setAttribute("aria-label", text);

    const step = (t) => {
      if (start === null) start = t;
      const p = Math.min((t - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 4);
      el.textContent = p < 1 ? prefix + format(target * eased) + suffix : text;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  /* Stagger table rows */
  root.querySelectorAll("tbody").forEach((tbody) => {
    Array.from(tbody.rows).forEach((row, i) => row.style.setProperty("--r", Math.min(i, 12)));
  });

  /* Scroll reveal */
  root.classList.add("dash-motion");
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        el.classList.add("is-visible");
        const counter = el.querySelector("[data-count]");
        if (counter) setTimeout(() => countUp(counter), 150 + (parseInt(el.style.getPropertyValue("--i")) || 0) * 70);
        io.unobserve(el);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );
  root.querySelectorAll("[data-reveal]").forEach((el) => io.observe(el));
})();