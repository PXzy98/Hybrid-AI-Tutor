// Applies the saved theme before the first paint, so a dark-mode user does not see a light frame.
// Keep in step with THEME_KEY and applyTheme() in src/components/theme.ts.
(function () {
  var saved = null;
  try {
    saved = window.localStorage.getItem("tutor.theme");
  } catch (e) {
    // storage blocked: follow the system setting
  }
  var dark = saved === "dark" ||
    (saved !== "light" && !!window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
})();
