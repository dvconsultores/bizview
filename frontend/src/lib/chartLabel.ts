/** Feature 056: category labels that fit the widths they are given.
 *
 * A horizontal bar used to cap its label column at `min(112, max(64, width * 0.28))` and draw the
 * text right-aligned, so a long name was cut at the left edge (`OLOGICOS PROVI…`) and the reader
 * lost its beginning. The column is measured now — up to 220 px and 40 % of the chart — and the text
 * is shortened at the end with an ellipsis, which keeps the part that identifies it.
 */

/** Leading symbols and spaces are data, so they are shown; they are trimmed only to measure and sort. */
export function trimLabel(label: string): string {
  return label.replace(/^[\s*·•-]+/, "").trim();
}

function fallbackWidth(text: string, fontPx: number): number {
  // jsdom and the first server render have no canvas: a per-character estimate keeps the column
  // stable and, more importantly, deterministic.
  let width = 0;
  for (const char of text) {
    width += (char === " " ? 0.32 : /[A-Z0-9]/.test(char) ? 0.66 : 0.55) * fontPx;
  }
  return width;
}

let context: CanvasRenderingContext2D | null | undefined;

/** Width of `text` in the font the charts draw with. */
export function measureText(text: string, fontPx = 11): number {
  if (context === undefined) {
    try {
      context = typeof document === "undefined"
        ? null
        : document.createElement("canvas").getContext("2d");
    } catch {
      context = null;
    }
  }
  if (context) {
    context.font = `500 ${fontPx}px "Plus Jakarta Sans", system-ui, sans-serif`;
    const measured = context.measureText(text).width;
    if (measured > 0) return measured;
  }
  return fallbackWidth(text, fontPx);
}

/** `text` when it fits, otherwise its longest prefix plus an ellipsis — never a left-side cut. */
export function fitLabel(text: string, maxPx: number, fontPx = 11): string {
  if (!text || maxPx <= 0) return "";
  if (measureText(text, fontPx) <= maxPx) return text;
  const chars = [...text];
  let low = 0;
  let high = chars.length;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    if (measureText(`${chars.slice(0, mid).join("").trimEnd()}…`, fontPx) <= maxPx) low = mid;
    else high = mid - 1;
  }
  if (low === 0) return "…";
  return `${chars.slice(0, low).join("").trimEnd()}…`;
}

export const LABEL_MIN = 96;
export const LABEL_MAX = 220;
/** Below this chart width the label moves above its bar instead of beside it (phones). */
export const LABEL_ABOVE = 480;

/** Width of the label column: 40 % of the chart at most, the widest label at most 220 px. */
export function labelColumn(width: number, labels: string[], fontPx = 11): number {
  const widest = labels.reduce((max, label) => Math.max(max, measureText(trimLabel(label), fontPx)), 0);
  const wanted = Math.min(width * 0.4, Math.min(LABEL_MAX, widest + 10));
  return Math.max(Math.min(LABEL_MIN, Math.max(0, width - 40)), Math.round(wanted));
}
