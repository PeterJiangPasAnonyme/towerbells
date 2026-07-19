(function () {
  async function applySiteConfig() {
    try {
      const res = await fetch("/api/config");
      if (!res.ok) return;
      const config = await res.json();
      if (config.admin_enabled) return;
      document.querySelectorAll(".admin-nav-link, .edit-link").forEach((el) => {
        el.classList.add("hidden");
        el.setAttribute("aria-hidden", "true");
      });
    } catch (_) {
      // Ignore config fetch failures on local/offline use.
    }
  }

  window.TowerbellsSiteConfig = { applySiteConfig };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applySiteConfig);
  } else {
    applySiteConfig();
  }
})();
