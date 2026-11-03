/* Feature 006: resolve the theme — and, feature 022, the language — before first paint (no flash). Same rules as
 * src/theme/resolve.ts and src/i18n/resolve.ts; a classic script loaded from <head> because the CSP forbids inline code. */
/* A cached value is only replayed when it cannot do anything but paint: characters a colour, a
 * radius or a shadow needs, and nothing that could open a rule, a string or a remote fetch. */
function isSafeValue(value) {
  return /^[A-Za-z0-9 .,%#()+\/-]{1,160}$/.test(value) && !/url\s*\(/i.test(value);
}

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

  /* Feature 051: the installation theme, replayed from the device cache so a reload paints it before
   * the first frame instead of flashing Clásico. src/theme/palette.ts writes this payload; /api/config
   * reconciles it afterwards. Anything unexpected is ignored: the CSS fallback is valid. */
  try {
    var raw = window.localStorage.getItem("bizview.theme.tokens");
    if (raw) {
      var payload = JSON.parse(raw);
      var fresh = payload && payload.version === 1 && payload.mode === theme &&
        typeof payload.at === "number" && Date.now() - payload.at < 30 * 24 * 60 * 60 * 1000;
      if (fresh && payload.vars) {
        var root = document.documentElement;
        for (var name in payload.vars) {
          if (Object.prototype.hasOwnProperty.call(payload.vars, name)) {
            var value = String(payload.vars[name]);
            if (/^[a-z0-9-]+$/.test(name) && isSafeValue(value)) {
              root.style.setProperty("--" + name, value);
            }
          }
        }
        if (payload.attrs) {
          for (var attr in payload.attrs) {
            if (Object.prototype.hasOwnProperty.call(payload.attrs, attr)) {
              root.setAttribute("data-" + attr.toLowerCase(), String(payload.attrs[attr]));
            }
          }
        }
        var band = String(payload.vars["c-chrome"] || "");
        if (meta && /^[0-9 ]{3,13}$/.test(band)) meta.setAttribute("content", "rgb(" + band + ")");
      }
    }
  } catch (e) { /* storage blocked or a stale payload: the stylesheet's fallback stands */ }

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
