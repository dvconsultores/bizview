/** Feature 063: the click-to-filter wiring a data card receives from the report screen. */
export interface CrossFilterState {
  enabled: boolean;
  /** The applied filters, keyed by dimension. */
  filters: Record<string, string[]>;
  /** Toggle/add one rendered value. `additive` is Ctrl/Cmd-click or a long press. */
  toggle: (dimension: string, value: string, additive: boolean) => void;
}

/** A dimension value as a mark needs it: the rendered label, the filter value, whether it is on. */
export interface MarkValue {
  dimension: string;
  value: string;
  selected: boolean;
}

export function markState(
  cross: CrossFilterState | undefined,
  dimension: string | undefined,
  value: string | null | undefined,
): MarkValue | null {
  if (!cross?.enabled || !dimension || value === null || value === undefined || value === "") {
    return null;
  }
  const selected = (cross.filters[dimension] ?? []).includes(value);
  return { dimension, value, selected };
}

/** Feature 063: the filters a mark click produces. A plain click is one cross-filter, so a value of
 * another dimension replaces whatever was filtered; Ctrl/Cmd-click keeps the others and adds to
 * the clicked dimension. Clicking the only selected value again clears it. */
export function toggledCrossFilter(
  filters: Record<string, string[]>,
  dimension: string,
  value: string,
  additive: boolean,
): Record<string, string[]> {
  const current = filters[dimension] ?? [];
  const values = additive
    ? current.includes(value)
      ? current.filter((entry) => entry !== value)
      : [...current, value]
    : current.length === 1 && current[0] === value
      ? []
      : [value];
  const next: Record<string, string[]> = additive ? { ...filters } : {};
  if (values.length > 0) next[dimension] = values;
  else delete next[dimension];
  return next;
}
