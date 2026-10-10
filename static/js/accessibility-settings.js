(() => {
  const key = "grapsy-accessibility-settings";
  const defaults = {textSize: "normal", highContrast: false, reducedMotion: false};
  let settings = {...defaults};

  try {
    const stored = JSON.parse(localStorage.getItem(key) || "{}");
    if (["normal", "large", "larger"].includes(stored.textSize)) settings.textSize = stored.textSize;
    settings.highContrast = stored.highContrast === true;
    settings.reducedMotion = stored.reducedMotion === true;
  } catch (_) {}

  function applySettings() {
    const root = document.documentElement;
    if (settings.textSize === "normal") root.removeAttribute("data-text-size");
    else root.dataset.textSize = settings.textSize;
    root.classList.toggle("a11y-high-contrast", settings.highContrast);
    root.classList.toggle("a11y-reduced-motion", settings.reducedMotion);

    const size = document.getElementById("accessibility-text-size");
    const contrast = document.getElementById("accessibility-contrast");
    const motion = document.getElementById("accessibility-motion");
    if (size) size.value = settings.textSize;
    if (contrast) contrast.checked = settings.highContrast;
    if (motion) motion.checked = settings.reducedMotion;
  }

  function saveSettings() {
    settings = {
      textSize: document.getElementById("accessibility-text-size")?.value || "normal",
      highContrast: document.getElementById("accessibility-contrast")?.checked || false,
      reducedMotion: document.getElementById("accessibility-motion")?.checked || false,
    };
    try { localStorage.setItem(key, JSON.stringify(settings)); } catch (_) {}
    applySettings();
  }

  applySettings();
  document.getElementById("accessibility-text-size")?.addEventListener("change", saveSettings);
  document.getElementById("accessibility-contrast")?.addEventListener("change", saveSettings);
  document.getElementById("accessibility-motion")?.addEventListener("change", saveSettings);
})();
