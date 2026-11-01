/** The themes a page can paint with (feature 047): the five the product ships, resolved locally, and
 * anything the installation uploaded or a project brought, fetched once and kept for the session.
 *
 * A report's theme is data that may not be in this build, so resolution is async; the caller paints
 * with the built-in default until the answer arrives rather than blocking the page. */
import { api } from "../api/client";
import type { ThemeRead } from "../api/types";
import { BUILTIN_THEMES, DEFAULT_THEME, isThemeId, type Theme } from "./themes";

export type ReportMode = "auto" | "light" | "dark";

const cache = new Map<string, Theme>();
const inFlight = new Map<string, Promise<Theme | null>>();

/** A theme already known without the network: a built-in, or one seen earlier this session. */
export function knownTheme(id: string | null | undefined): Theme | null {
  if (!id) return null;
  return cache.get(id) ?? (isThemeId(id) ? BUILTIN_THEMES[id] : null);
}

export function forgetTheme(id: string): void {
  cache.delete(id);
  inFlight.delete(id);
}

/** The authored tokens of any theme id, from this build or from the installation. */
export function loadTheme(id: string): Promise<Theme | null> {
  if (isThemeId(id)) return Promise.resolve(BUILTIN_THEMES[id]);
  const cached = cache.get(id);
  if (cached) return Promise.resolve(cached);
  const running = inFlight.get(id);
  if (running) return running;
  const request = api
    .get<ThemeRead>(`/api/themes/${encodeURIComponent(id)}`)
    .then((read) => {
      cache.set(id, read.tokens);
      return read.tokens;
    })
    .catch(() => null)
    .finally(() => inFlight.delete(id));
  inFlight.set(id, request);
  return request;
}

/** Report → installation → the product's default. An unknown id is ignored, never fatal: a page
 * whose theme was deleted keeps rendering with the installation's. */
export function reportThemeId(
  declared: { id?: string | null; palette?: string | null } | null | undefined,
  installation?: string | null,
): string {
  const own = declared?.id || declared?.palette;
  if (own) return own;
  return installation || DEFAULT_THEME;
}

/** `layout.theme.mode`: `auto` follows the app's resolved appearance. */
export function reportMode(declared: { mode?: string | null } | null | undefined): ReportMode {
  const mode = declared?.mode;
  return mode === "light" || mode === "dark" ? mode : "auto";
}

const MODE_KEY = "bizview.report-mode.";

/** The viewer's light/dark choice for one report, kept for this browser session (047 FR-019). It
 * wins over the report's `layout.theme.mode` and over the application's appearance. */
export function readViewerMode(reportId: string): "light" | "dark" | null {
  try {
    const value = window.sessionStorage.getItem(MODE_KEY + reportId);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function writeViewerMode(reportId: string, mode: "light" | "dark" | null): void {
  try {
    if (mode) window.sessionStorage.setItem(MODE_KEY + reportId, mode);
    else window.sessionStorage.removeItem(MODE_KEY + reportId);
  } catch {
    // A browser with storage disabled keeps the choice for the page's lifetime only.
  }
}
