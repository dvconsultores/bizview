/** Theme rules (feature 006). public/theme-init.js repeats them before the app loads; keep both
 * in step (tests/unit/theme.test.ts runs the two against the same cases). */
export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export const THEME_PREFERENCES: readonly ThemePreference[] = ["system", "light", "dark"];
export const STORAGE_KEY = "bizview.theme";
const HERO_COLOR: Record<ResolvedTheme, string> = { light: "#3a7393", dark: "#172b37" };
const DARK_QUERY = "(prefers-color-scheme: dark)";

export const isPreference = (v: unknown): v is ThemePreference =>
  typeof v === "string" && (THEME_PREFERENCES as readonly string[]).includes(v);

export const resolveTheme = (pref: ThemePreference, prefersDark: boolean): ResolvedTheme =>
  pref === "system" ? (prefersDark ? "dark" : "light") : pref;

export function darkQuery(): MediaQueryList | null {
  try {
    return typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
  } catch {
    return null;
  }
}

export const systemPrefersDark = (): boolean => darkQuery()?.matches ?? false;

/** The last choice on this device; storage may be blocked (private mode) → "system". */
export function readCachedPreference(): ThemePreference {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return isPreference(v) ? v : "system";
  } catch {
    return "system";
  }
}

export function writeCachedPreference(pref: ThemePreference): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    /* storage blocked: the theme still applies for this page */
  }
}

export function applyTheme(theme: ResolvedTheme): void {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", HERO_COLOR[theme]);
}
