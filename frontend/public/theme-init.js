/* Feature 006: resolve the theme — and, feature 022, the language — before first paint (no flash). Same rules as
 * src/theme/resolve.ts and src/i18n/resolve.ts; a classic script loaded from <head> because the CSP forbids inline code. */
(function () {
  var pref = "system";
  try {
    var v = window.localStorage.getItem("bizview.theme");
    if (v === "light" || v === "dark" || v === "system") pref = v;
  } catch (e) { /* storage blocked: follow the device */ }
  var dark = pref === "dark";
  if (pref === "system") {
    try { dark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) { dark = false; }
  }
  var theme = dark ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? "#172b37" : "#3a7393");

  /* Feature 022 (FR-011): <html lang> before first paint, same rules as src/i18n/resolve.ts (device cache, then browser); the account value replaces it after /api/me. */
  var lang = null;
  try {
    var lv = window.localStorage.getItem("bizview.locale");
    if (lv === "es" || lv === "en") lang = lv;
  } catch (e) { /* storage blocked: follow the browser */ }
  if (!lang) {
    var langs = (navigator.languages && navigator.languages.length) ? navigator.languages : [navigator.language];
    for (var i = 0; i < langs.length; i++) {
      var tag = String(langs[i]);
      var primary = tag.split(/[-_]/)[0];
      if (primary) primary = primary.toLowerCase();
      if (primary === "es" || primary === "en") { lang = primary; break; }
    }
  }
  if (lang) document.documentElement.setAttribute("lang", lang);
})();
