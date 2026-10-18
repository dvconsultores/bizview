import { useLayoutEffect, useState, type RefObject } from "react";

/** Geometry, ticks and null-gap paths shared by every report chart (feature 026, research R5), so
 * `TrendChart` and the layout's chart kinds draw the same figure the same way. */

/** Height of a full chart. The layout contract keeps every chart at 160 px or more. */
export const CHART_HEIGHT = 200;
export const CHART_MIN_HEIGHT = 160;
export const PAD = { top: 12, right: 10, bottom: 26, left: 44 };

export function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) {
    max = min + 1;
    min = Math.min(0, min);
  }
  const step0 = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const start = Math.floor(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step * 0.5; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

/** Element width in px (the fallback until the first measure), kept in step by a ResizeObserver. */
export function useChartWidth(ref: RefObject<HTMLDivElement | null>, fallback = 320): number {
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => {
      const w = Math.floor(el.clientWidth);
      setWidth(w > 0 ? w : fallback);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fallback]);

  return width;
}

export interface ChartScale {
  ticks: number[];
  innerW: number;
  innerH: number;
  /** Horizontal position of bucket/category index `i`. */
  x: (i: number) => number;
  /** Vertical position of a value. */
  y: (value: number) => number;
}

/** Linear scale over the full value range (zero included); gaps are ignored when measuring. */
export function chartScale(
  values: readonly (number | null | undefined)[],
  count: number,
  width: number,
  height = CHART_HEIGHT,
): ChartScale {
  const numbers = values.filter((v): v is number => v !== null && v !== undefined);
  const lo = Math.min(0, ...numbers);
  const hi = Math.max(0, ...numbers);
  const ticks = niceTicks(lo, hi);
  const innerW = width - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const n = Math.max(1, count - 1);
  const last = (ticks[ticks.length - 1] - ticks[0]) || 1;
  return {
    ticks,
    innerW,
    innerH,
    x: (i) => PAD.left + (count === 1 ? innerW / 2 : (i / n) * innerW),
    y: (value) => PAD.top + innerH - ((value - ticks[0]) / last) * innerH,
  };
}

/** `M`/`L` path broken at every gap, so a bucket without data leaves a hole instead of a line. */
export function gapPath(
  values: readonly (number | null | undefined)[],
  x: (i: number) => number,
  y: (v: number) => number,
): string {
  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (v === null || v === undefined) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

/** Value range of one slice of the data, zero included. */
export function valueRange(values: readonly (number | null | undefined)[]): [number, number] {
  const numbers = values.filter((v): v is number => v !== null && v !== undefined);
  return [Math.min(0, ...numbers), Math.max(0, ...numbers)];
}

/** Indices of the category labels drawn under an axis: first, middle and last, trimmed when the
 * chart is too narrow for every label. */
export function axisLabelIndexes(count: number, most = 12): number[] {
  if (count <= 0) return [];
  if (count === 1) return [0];
  if (count <= most) return Array.from({ length: count }, (_, i) => i);
  const step = Math.ceil(count / most);
  const out: number[] = [];
  for (let i = 0; i < count; i += step) out.push(i);
  if (out[out.length - 1] !== count - 1 && count - 1 - out[out.length - 1] >= step / 2) out.push(count - 1);
  return out;
}
