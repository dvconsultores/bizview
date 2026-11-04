import { isPaletteId } from "../theme/palette";
import type { ThemeMode } from "../theme/themes";

/** The reader's own view of a report (feature 053): the palette preview and light/dark.
 *
 * Both are view-only — the report definition is data an author declares (047, IX) — and both live
 * in the URL next to the filter selection, so a chip, a reload and a shared tab show the same
 * report. An unknown value is ignored, never fatal: the declared/installed one applies. */
export interface ReportViewState {
  /** A palette preset the reader picked for this view, or `null` for the declared/installed one. */
  theme: string | null;
  /** The reader's light/dark, or `null` for the report's own mode (auto when it declares none). */
  mode: ThemeMode | null;
}

export type ReportPanel = "filters" | "params";

export const EMPTY_VIEW_STATE: ReportViewState = { theme: null, mode: null };

/** The report page's one sheet (feature 053): an opener shows its own tab, and pressing the tab
 * that is already shown closes the sheet. */
export function togglePanel(current: ReportPanel | null, target: ReportPanel): ReportPanel | null {
  return current === target ? null : target;
}

export function parseViewState(params: URLSearchParams): ReportViewState {
  const theme = params.get("theme");
  const mode = params.get("mode");
  return {
    theme: isPaletteId(theme) ? theme : null,
    mode: mode === "light" || mode === "dark" ? mode : null,
  };
}

/** A copy of `params` with one view key set (or removed when the value is `null`). */
export function withViewState(
  params: URLSearchParams,
  change: Partial<ReportViewState>,
): URLSearchParams {
  const next = new URLSearchParams(params);
  for (const [key, value] of Object.entries(change)) {
    if (value === null) next.delete(key);
    else next.set(key, String(value));
  }
  return next;
}

/** Whether the reader is looking at the report exactly as it was declared. */
export function isDefaultViewState(
  state: ReportViewState,
  declaredTheme: string | null,
): boolean {
  return (state.theme ?? declaredTheme) === declaredTheme && state.mode === null;
}
