/**
 * Feature 065: the snippet of a widget, held in memory for this page only (FR-002).
 *
 * The snippet carries the widget's key, and the key is never stored readable, so it must never reach
 * browser storage: it is shown at creation and at replacement, and the in-product test page can show
 * it only during the page session in which that happened. A reload, a new tab or another device never
 * has it, which is why the test page explains that the snippet was shown once and can be replaced.
 */
interface Held {
  code: string;
  id: number;
  snippet: string;
}

let held: Held | null = null;

/** Called by the panel when the API answers a creation or a replacement; it replaces any previous
 * one. */
export function holdSnippet(code: string, id: number, snippet: string): void {
  held = { code, id, snippet };
}

/**
 * The snippet for this widget, while the page that created or replaced it is still open, or null.
 *
 * Reading does not consume it: React's StrictMode renders a component twice in development, and a
 * destructive read would lose the snippet on the second render. It is overwritten by the next
 * creation/replacement and disappears with the page.
 */
export function heldSnippet(code: string, id: number): string | null {
  return held && held.code === code && held.id === id ? held.snippet : null;
}
