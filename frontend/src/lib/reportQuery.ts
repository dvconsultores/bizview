import type { CompareMode, PeriodPreset, ReportDefinition } from "../api/types";
import { t } from "../i18n/live";

export interface ReportSelection {
  period: PeriodPreset;
  from: string;
  to: string;
  compare: CompareMode;
  filters: Record<string, string[]>;
}

export const MAX_FILTER_VALUES = 50;

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function compareChoices(def: ReportDefinition): CompareMode[] {
  const deduped = Array.from(new Set<CompareMode>(def.compare.allowed));
  if (!deduped.includes(def.compare.default)) {
    deduped.unshift(def.compare.default);
  }
  if (deduped.length === 0) {
    deduped.push(def.compare.default);
  }
  return deduped;
}

export function defaultSelection(def: ReportDefinition): ReportSelection {
  return {
    period: def.periods.default,
    from: "",
    to: "",
    compare: def.compare.default,
    filters: {},
  };
}

export function parseSelection(params: URLSearchParams, def: ReportDefinition): ReportSelection {
  const allowedPeriods = new Set<PeriodPreset>(def.periods.allowed);
  allowedPeriods.add(def.periods.default);
  const periodParam = params.get("period") as PeriodPreset | null;
  const period: PeriodPreset = periodParam && allowedPeriods.has(periodParam) ? periodParam : def.periods.default;

  const allowedCompare = new Set<CompareMode>(compareChoices(def));
  const compareParam = params.get("compare") as CompareMode | null;
  const compare: CompareMode = compareParam && allowedCompare.has(compareParam) ? compareParam : def.compare.default;

  let from = "";
  let to = "";
  if (period === "custom") {
    const rawFrom = params.get("from") ?? "";
    const rawTo = params.get("to") ?? "";
    if (DATE_RE.test(rawFrom)) from = rawFrom;
    if (DATE_RE.test(rawTo)) to = rawTo;
  }

  const filters: Record<string, string[]> = {};
  for (const id of def.filters) {
    const rawValues = params.getAll(`filter.${id}`);
    const seen = new Set<string>();
    const values: string[] = [];
    for (const raw of rawValues) {
      if (raw === "" || seen.has(raw)) continue;
      seen.add(raw);
      values.push(raw);
      if (values.length >= MAX_FILTER_VALUES) break;
    }
    if (values.length > 0) filters[id] = values;
  }

  return { period, from, to, compare, filters };
}

export function serializeSelection(s: ReportSelection, def?: ReportDefinition): URLSearchParams {
  const params = new URLSearchParams();
  params.set("period", s.period);
  params.set("compare", s.compare);
  if (s.period === "custom") {
    if (s.from) params.set("from", s.from);
    if (s.to) params.set("to", s.to);
  }

  const ids = def ? def.filters : Object.keys(s.filters).sort();
  for (const id of ids) {
    const values = s.filters[id] ?? [];
    for (const value of values) {
      params.append(`filter.${id}`, value);
    }
  }

  return params;
}

export function selectionQuery(s: ReportSelection, def?: ReportDefinition): string {
  return `?${serializeSelection(s, def).toString()}`;
}

export function filterOptionsQuery(s: ReportSelection, q?: string): string {
  const params = new URLSearchParams();
  params.set("period", s.period);
  if (s.period === "custom") {
    if (s.from) params.set("from", s.from);
    if (s.to) params.set("to", s.to);
  }
  params.set("compare", "none");
  const trimmedQ = q?.trim() ?? "";
  if (trimmedQ !== "") params.set("q", trimmedQ);
  return `?${params.toString()}`;
}

function arraysEqualIgnoreOrder(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const aSorted = [...a].sort();
  const bSorted = [...b].sort();
  for (let i = 0; i < aSorted.length; i++) {
    if (aSorted[i] !== bSorted[i]) return false;
  }
  return true;
}

export function sameSelection(a: ReportSelection, b: ReportSelection): boolean {
  if (a.period !== b.period) return false;
  if (a.compare !== b.compare) return false;
  if (a.period === "custom") {
    if (a.from !== b.from || a.to !== b.to) return false;
  }
  const keys = new Set([...Object.keys(a.filters), ...Object.keys(b.filters)]);
  for (const key of keys) {
    const aValues = a.filters[key] ?? [];
    const bValues = b.filters[key] ?? [];
    if (!arraysEqualIgnoreOrder(aValues, bValues)) return false;
  }
  return true;
}

export function countChanges(draft: ReportSelection, applied: ReportSelection): number {
  let changes = 0;
  if (draft.period !== applied.period) {
    changes += 1;
  } else if (draft.period === "custom" && (draft.from !== applied.from || draft.to !== applied.to)) {
    changes += 1;
  }
  if (draft.compare !== applied.compare) changes += 1;
  const keys = new Set([...Object.keys(draft.filters), ...Object.keys(applied.filters)]);
  for (const key of keys) {
    const draftValues = draft.filters[key] ?? [];
    const appliedValues = applied.filters[key] ?? [];
    if (!arraysEqualIgnoreOrder(draftValues, appliedValues)) changes += 1;
  }
  return changes;
}

export function countActiveFilters(s: ReportSelection): number {
  let count = 0;
  for (const values of Object.values(s.filters)) {
    count += values.length;
  }
  return count;
}

export function isIncompleteCustom(s: ReportSelection): boolean {
  return s.period === "custom" && (s.from === "" || s.to === "");
}

export interface RangeErrors {
  from?: string;
  to?: string;
}

export function validateSelection(s: ReportSelection): RangeErrors {
  if (s.period !== "custom") return {};
  const errors: RangeErrors = {};
  if (s.from === "") errors.from = t.reportParams.fromRequired;
  if (s.to === "") errors.to = t.reportParams.toRequired;
  if (s.from !== "" && s.to !== "" && s.to < s.from) {
    errors.to = t.reportParams.toBeforeFrom;
  }
  return errors;
}

export function withFilterValues(
  s: ReportSelection,
  id: string,
  values: string[],
): ReportSelection {
  const newFilters = { ...s.filters };
  const deduped = Array.from(new Set(values.filter((v) => v !== "")));
  const capped = deduped.slice(0, MAX_FILTER_VALUES);
  if (capped.length === 0) {
    delete newFilters[id];
  } else {
    newFilters[id] = capped;
  }
  return { ...s, filters: newFilters };
}

export function withoutFilterValue(
  s: ReportSelection,
  id: string,
  value: string,
): ReportSelection {
  const current = s.filters[id] ?? [];
  const next = current.filter((v) => v !== value);
  return withFilterValues(s, id, next);
}
