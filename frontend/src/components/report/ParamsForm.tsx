import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import type { CompareMode, PeriodPreset, ReportDefinition } from "../../api/types";
import {
  compareChoices,
  countChanges,
  defaultSelection,
  isIncompleteCustom,
  sameSelection,
  selectionQuery,
  validateSelection,
  withFilterValues,
  type ReportSelection,
} from "../../lib/reportQuery";
import { useT } from "../../i18n";
import { localized } from "../../lib/labels";
import { Button } from "../Button";
import { Input } from "../Input";
import { MultiSelect, type MultiSelectOptions } from "../MultiSelect";
import { Select } from "../Select";

export interface ParamsFormProps {
  def: ReportDefinition;
  applied: ReportSelection;
  onApply: (s: ReportSelection) => void;
  loadOptions: (
    filterId: string,
    period: ReportSelection,
    q: string,
    signal: AbortSignal,
  ) => Promise<MultiSelectOptions>;
  children?: ReactNode;
  className?: string;
  /** Feature 030: apply as the reader edits (250 ms debounce) instead of on "Aplicar". */
  live?: boolean;
  /** Feature 030: render only the period block or only the filter block (the filters sheet). */
  section?: "all" | "period" | "filters";
  /** `bar` lays the controls out in one compact row (the report page's parameter panel). */
  variant?: "stacked" | "bar";
}

export function ParamsForm({
  def,
  applied,
  onApply,
  loadOptions,
  children,
  className,
  live = false,
  section = "all",
  variant = "stacked",
}: ParamsFormProps) {
  const t = useT();
  const [draft, setDraft] = useState<ReportSelection>(applied);
  const [showErrors, setShowErrors] = useState(false);
  const lastAppliedKeyRef = useRef(selectionQuery(applied, def));
  const fromInputRef = useRef<HTMLInputElement>(null);
  const toInputRef = useRef<HTMLInputElement>(null);
  const filtersSectionId = useId();

  useEffect(() => {
    const currentKey = selectionQuery(applied, def);
    if (currentKey !== lastAppliedKeyRef.current) {
      lastAppliedKeyRef.current = currentKey;
      setDraft(applied);
      setShowErrors(false);
    }
  }, [applied, def]);

  const pending = useMemo(
    () => countChanges(draft, applied),
    [draft, applied],
  );

  const errors = useMemo(
    () => (showErrors ? validateSelection(draft) : {}),
    [showErrors, draft],
  );

  // Feature 030 (FR-004): the sheet applies live — one request per 250 ms burst, and only when the
  // draft is complete (an incomplete custom range or a missing date is never sent).
  useEffect(() => {
    if (!live || pending === 0) return;
    if (Object.keys(validateSelection(draft)).length > 0 || isIncompleteCustom(draft)) return;
    const id = window.setTimeout(() => onApply(draft), 250);
    return () => window.clearTimeout(id);
  }, [live, draft, pending, onApply]);

  const optionsBase = useMemo(() => {
    const baseIsComplete =
      Object.keys(validateSelection(draft)).length === 0 &&
      !isIncompleteCustom(draft);
    return baseIsComplete ? draft : applied;
  }, [draft, applied]);

  const optionsReloadKey = `${optionsBase.period}|${optionsBase.from}|${optionsBase.to}`;

  const periodOptions = useMemo(() => {
    const allowed = [...def.periods.allowed];
    if (!allowed.includes(def.periods.default)) {
      allowed.unshift(def.periods.default);
    }
    return allowed;
  }, [def.periods.allowed, def.periods.default]);

  const compareOptions = useMemo(
    () => compareChoices(def),
    [def],
  );

  const periodLabels = t.reportParams.periodLabels;
  const compareLabels = t.reportParams.compareLabels;

  const handlePeriodChange = (nextPeriod: PeriodPreset) => {
    setDraft((prev) => ({
      ...prev,
      period: nextPeriod,
      from: nextPeriod === "custom" ? prev.from : "",
      to: nextPeriod === "custom" ? prev.to : "",
    }));
  };

  const handleCompareChange = (nextCompare: CompareMode) => {
    setDraft((prev) => ({ ...prev, compare: nextCompare }));
  };

  const handleFilterChange = (filterId: string, values: string[]) => {
    setDraft((prev) => withFilterValues(prev, filterId, values));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationErrors = validateSelection(draft);
    if (Object.keys(validationErrors).length > 0) {
      setShowErrors(true);
      if (validationErrors.from) {
        fromInputRef.current?.focus();
      } else if (validationErrors.to) {
        toInputRef.current?.focus();
      }
      return;
    }
    setShowErrors(false);
    onApply(draft);
  };

  const handleClear = () => {
    const defaults = defaultSelection(def);
    setDraft(defaults);
    setShowErrors(false);
    if (!sameSelection(defaults, applied)) {
      onApply(defaults);
    }
  };

  const getFilterLoader = useCallback(
    (filterId: string) => {
      return (q: string, signal: AbortSignal) =>
        loadOptions(filterId, optionsBase, q, signal);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loadOptions, optionsReloadKey],
  );

  const filterLoaders = useMemo(() => {
    const loaders: Record<string, (q: string, signal: AbortSignal) => Promise<MultiSelectOptions>> = {};
    for (const filterId of def.filters) {
      loaders[filterId] = getFilterLoader(filterId);
    }
    return loaders;
  }, [def.filters, getFilterLoader]);

  const renderFilter = (filterId: string) => (
    <MultiSelect
      key={filterId}
      label={localized(def.dimensions[filterId], "label") ?? filterId}
      values={draft.filters[filterId] ?? []}
      onChange={(values) => handleFilterChange(filterId, values)}
      loadOptions={filterLoaders[filterId]}
      reloadKey={optionsReloadKey}
    />
  );
  // Feature 030 edge case: with 10+ filters the tail sits under a collapsible heading.
  const grouped = def.filters.length >= 10;
  const shownFilters = grouped ? def.filters.slice(0, 6) : def.filters;

  const bar = variant === "bar";
  const row = bar ? "flex flex-wrap items-end gap-3" : undefined;
  const heading = (text: string) =>
    bar ? null : (
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{text}</h3>
    );
  const field = bar ? "min-w-[8.5rem] flex-1" : undefined;

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      className={className}
      data-testid="params-form"
      data-variant={variant}
    >
      <div className={row}>
        {section !== "filters" && (
          <div className={bar ? "contents" : "space-y-4"}>
            {heading(t.reportParams.periodSection)}

            <div className={field}>
              <Select
                label={t.reportParams.period}
                value={draft.period}
                onChange={(e) => handlePeriodChange(e.target.value as PeriodPreset)}
              >
                {periodOptions.map((period) => (
                  <option key={period} value={period}>
                    {periodLabels[period] ?? period}
                  </option>
                ))}
              </Select>
            </div>

            {draft.period === "custom" && (
              <div className={bar ? "flex min-w-[15rem] flex-1 gap-3" : "grid grid-cols-1 gap-4 min-[360px]:grid-cols-2"}>
                <Input
                  ref={fromInputRef}
                  label={t.reportParams.from}
                  type="date"
                  required
                  value={draft.from}
                  max={draft.to || undefined}
                  error={errors.from}
                  onChange={(e) => setDraft((prev) => ({ ...prev, from: e.target.value }))}
                />
                <Input
                  ref={toInputRef}
                  label={t.reportParams.to}
                  type="date"
                  required
                  value={draft.to}
                  min={draft.from || undefined}
                  error={errors.to}
                  onChange={(e) => setDraft((prev) => ({ ...prev, to: e.target.value }))}
                />
              </div>
            )}
          </div>
        )}

        {section !== "filters" && (
          <div className={bar ? "contents" : "mt-5 space-y-4 border-t border-line pt-5"}>
            {heading(t.reportParams.compareSection)}

            <div className={field}>
              {compareOptions.length > 1 ? (
                <Select
                  label={t.reportParams.compare}
                  value={draft.compare}
                  onChange={(e) => handleCompareChange(e.target.value as CompareMode)}
                >
                  {compareOptions.map((compare) => (
                    <option key={compare} value={compare}>
                      {compareLabels[compare] ?? compare}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  label={t.reportParams.compare}
                  readOnly
                  value={compareLabels[compareOptions[0]] ?? compareOptions[0]}
                />
              )}
            </div>
          </div>
        )}

        {section !== "period" && def.filters.length > 0 && (
          <section
            aria-labelledby={filtersSectionId}
            className={bar ? "contents" : "mt-5 space-y-4 border-t border-line pt-5"}
          >
            {heading(t.reportParams.filtersSection)}

            {shownFilters.map(renderFilter)}
            {grouped ? (
              <details className="rounded-xl border border-line p-3">
                <summary className="flex min-h-tap cursor-pointer items-center text-sm font-medium text-ink">
                  {t.reportSheet.moreFilters(def.filters.length - shownFilters.length)}
                </summary>
                <div className="mt-3 space-y-4">{def.filters.slice(shownFilters.length).map(renderFilter)}</div>
              </details>
            ) : null}
          </section>
        )}

        {children}
      </div>

      {bar ? null : (
        <footer className="mt-5 flex flex-col gap-3 border-t border-line pt-5">
          {live ? null : (
            <>
              <p role="status" className="text-sm text-ink-muted" data-testid="pending-status">
                {pending === 0 ? t.reportParams.noPending : t.reportParams.pending(pending)}
              </p>
              <Button type="submit" variant="primary" block disabled={pending === 0}>
                {t.reportParams.apply}
              </Button>
            </>
          )}
          <Button type="button" variant="secondary" block onClick={handleClear}>
            {t.reportParams.clear}
          </Button>
        </footer>
      )}
    </form>
  );
}
