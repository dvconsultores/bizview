import { CalendarClock, FileDown, History, Mail, Moon, Share2, Sun, Tv } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { api, ApiError } from "../api/client";
import type {
  Dashboard,
  EmailOptions,
  ReportData,
  ReportDefinition,
} from "../api/types";
import { Alert } from "../components/Alert";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { PageHeader } from "../components/PageHeader";
import { ReportViews, SingleView, VIEW_CARD_PREFIX } from "../components/report/ReportViews";
import type { CrossFilterState } from "../components/report/crossFilter";
import { cardTitle } from "../lib/cardTitle";
import { CardDialog } from "../components/report/CardDialog";
import { LayoutRenderer } from "../components/report/LayoutRenderer";
import { downloadCardPng } from "../lib/cardPng";
import type { LayoutParamsWiring } from "../components/report/LayoutBlocks";
import { Spinner } from "../components/Spinner";
import { ParamsForm } from "../components/report/ParamsForm";
import { ReportActions } from "../components/report/ReportActions";
import { ReportArea } from "../components/report/ReportArea";
import { ReportMetaLine } from "../components/report/ReportMetaLine";
import { ReportSheet } from "../components/report/ReportSheet";
import { ReportParamsPanel } from "../components/report/ReportParamsPanel";
import type { ParameterChip } from "../components/report/ParameterChips";
import { Button } from "../components/Button";
import { View } from "../components/View";
import type { MultiSelectOptions } from "../components/MultiSelect";
import { useAuth } from "../auth/AuthContext";
import { recordRecent } from "../lib/dashboardPrefs";
import { readViewerMode, reportMode, writeViewerMode, type ReportMode } from "../theme/library";
import type { ThemeMode } from "../theme/themes";
import { t as liveT, useT } from "../i18n";
import { localized } from "../lib/labels";
import {
  csvFileName,
  downloadCsv,
  toCsv,
  toCsvSections,
  viewCsvTable,
  type CsvTable,
} from "../lib/csv";
import {
  parseViewState,
  togglePanel,
  withViewState,
  type ReportViewState,
} from "../lib/reportView";
import {
  defaultSelection,
  filterOptionsQuery,
  isIncompleteCustom,
  unknownFilterIds,
  parseSelection,
  sameSelection,
  selectionQuery,
  serializeSelection,
  withoutFilterValue,
  type ReportSelection,
} from "../lib/reportQuery";
import {
  formatClock,
  useAutoRefresh,
  useAutoRefreshMode,
} from "../lib/autoRefresh";
import { AutoRefreshStatusLine } from "../components/report/AutoRefreshControl";
import { TvLayout } from "../components/report/TvLayout";
import { useHideShellChrome } from "../components/ShellChrome";
import {
  enterFullscreen,
  exitFullscreen,
  fullscreenSupported,
  isFullscreen,
  onFullscreenChange,
} from "../lib/fullscreen";
import { freshnessText, isStale, staleText } from "../lib/freshness";
import { formatRange } from "../lib/numbers";
import { useToast } from "../components/Toast";
import { useTheme } from "../theme/ThemeContext";
import { EmailSendPanel } from "../components/sharing/EmailSendPanel";
import { SendHistoryPanel } from "../components/sharing/SendHistory";
import { ShareLinksPanel } from "../components/sharing/ShareLinksPanel";
import { SubscriptionsPanel } from "../components/sharing/SubscriptionsPanel";

async function downloadPdf(
  id: string,
  query: string,
  filename: string,
  defaultMessage: string,
) {
  const res = await fetch(`/api/reports/${encodeURIComponent(id)}/pdf${query}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-Requested-With": "fetch" },
  });
  if (!res.ok) {
    let message = defaultMessage;
    try {
      message = (await res.json()).error?.message ?? defaultMessage;
    } catch {
      /* not JSON */
    }
    throw new Error(message);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Report definitions already loaded in this tab (by report id). */
const definitionCache = new Map<string, ReportDefinition>();

export function ReportView() {
  const t = useT();
  const { user } = useAuth();
  const toast = useToast();
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const [def, setDef] = useState<ReportDefinition | null>(null);
  const [data, setData] = useState<ReportData | null>(null);
  const [dataQuery, setDataQuery] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  // Feature 030: filters open the side/bottom sheet; parameters open a compact inline panel.
  const [panel, setPanel] = useState<"filters" | "params" | null>(null);
  const { setPalette, tokens, resolved } = useTheme();
  const [shownAt, setShownAt] = useState<Date | null>(null);
  const [storedMode, setStoredMode] = useAutoRefreshMode(id);
  const [fs, setFs] = useState(() => isFullscreen());
  const enteredFsRef = useRef(false);
  const exitTvRef = useRef<() => void>(() => undefined);

  const queryRef = useRef<string | null>(null);
  const versionRef = useRef<string | null>(null);
  const loadingRef = useRef(false);

  const tv = params.get("tv") === "1";

  // Feature 056: one card full screen, shareable as `?ampliar=<component id>`; TV mode ignores it.
  const maximizedId = tv ? null : params.get("ampliar");
  const maximize = useCallback((id: string, replace = false) => {
    const next = new URLSearchParams(params);
    next.set("ampliar", id);
    setParams(next, { replace });
  }, [params, setParams]);
  const closeMaximized = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete("ampliar");
    setParams(next, { replace: true });
  }, [params, setParams]);


  // Feature 053: one sheet, two tabs. Both actions open it on their tab; pressing the tab that is
  // already shown closes it (the toggle the report page always had).
  const openFilters = useCallback(() => setPanel((current) => togglePanel(current, "filters")), []);
  const toggleParams = useCallback(() => setPanel((current) => togglePanel(current, "params")), []);
  const closePanel = useCallback(() => setPanel(null), []);

  /** The report's own theme (`layout.theme.id`, or its deprecated alias `palette`) wins over the
   * installation's; the selector in Parámetros applies a viewer-side preview until the declared
   * value is edited in the project. */
  const declaredTheme = def?.layout?.theme;
  const declaredPalette = declaredTheme?.id ?? declaredTheme?.palette ?? null;
  const declaredMode: ReportMode = reportMode(declaredTheme);
  /** The reader's own palette and light/dark for this view (053): URL first, then the stored choice
   * for this report, then what the report declares. */
  const viewState = useMemo<ReportViewState>(() => {
    const fromUrl = parseViewState(params);
    return { theme: fromUrl.theme, mode: fromUrl.mode ?? readViewerMode(id) };
  }, [params, id]);
  const setView = useCallback(
    (change: Partial<ReportViewState>) => {
      if (change.mode !== undefined) writeViewerMode(id, change.mode);
      setParams(withViewState(params, change), { replace: true });
    },
    [id, params, setParams],
  );
  useEffect(() => {
    setPalette(viewState.theme ?? declaredPalette);
  }, [viewState.theme, declaredPalette, setPalette]);
  useEffect(() => () => setPalette(null), [setPalette]);
  const areaMode: ThemeMode =
    viewState.mode ?? (declaredMode === "auto" ? resolved : declaredMode);
  const toggleMode = () => {
    const next: ThemeMode = areaMode === "dark" ? "light" : "dark";
    setView({ mode: next });
  };

  // TV mode is meant to be looked at, not worked in: the chrome steps aside with it.
  useHideShellChrome(tv);

  useEffect(() => {
    return onFullscreenChange(() => {
      const now = isFullscreen();
      setFs(now);
      if (!now && enteredFsRef.current) {
        enteredFsRef.current = false;
        exitTvRef.current();
      }
    });
  }, []);

  useEffect(() => {
    if (!tv) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        exitTvRef.current();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [tv]);

  // A definition seen before is used at once (the data request starts without waiting) and
  // refreshed in the background; the page only updates if it changed (a new version applied).
  useEffect(() => {
    let cancelled = false;
    const known = definitionCache.get(id);
    setDef(known ?? null);
    setError(null);
    api
      .get<ReportDefinition>(`/api/reports/${encodeURIComponent(id)}`)
      .then((d) => {
        if (cancelled) return;
        definitionCache.set(id, d);
        if (!known || JSON.stringify(known) !== JSON.stringify(d)) setDef(d);
      })
      .catch((e) => {
        if (cancelled) return;
        definitionCache.delete(id);
        setDef(null);
        setError(e instanceof ApiError ? e.message : t.common.unexpected);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Opened successfully: listed under "Recientes" on the home page (this user, this device).
  const loaded = def !== null;
  useEffect(() => {
    if (loaded && user) recordRecent(user.id, `/r/${id}`);
  }, [loaded, user, id]);

  const [sharePanel, setSharePanel] = useState<
    "share" | "email" | "sends" | "schedules" | null
  >(null);
  const [dashCode, setDashCode] = useState<string | null>(null);
  const [emailAvailable, setEmailAvailable] = useState(false);

  useEffect(() => {
    setSharePanel(null);
    let cancelled = false;
    void (async () => {
      try {
        const dashboards = await api.get<{ items: Dashboard[] }>(
          "/api/dashboards",
        );
        if (cancelled) return;
        const match = dashboards.items.find(
          (dashboard) => dashboard.path === `/r/${id}`,
        );
        if (!match) {
          setDashCode(null);
          setEmailAvailable(false);
          return;
        }
        setDashCode(match.code);
        try {
          const emailOptions = await api.get<EmailOptions>(
            `/api/dashboards/${encodeURIComponent(match.code)}/email`,
          );
          if (!cancelled) setEmailAvailable(emailOptions.available);
        } catch {
          if (!cancelled) setEmailAvailable(false);
        }
      } catch {
        if (!cancelled) {
          setDashCode(null);
          setEmailAvailable(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const applied = useMemo(
    () => (def ? parseSelection(params, def) : null),
    [params, def],
  );
  const incompleteCustom = applied ? isIncompleteCustom(applied) : false;
  const unknownFilters = useMemo(() => (def ? unknownFilterIds(params, def) : []), [params, def]);
  const query =
    applied && def && !incompleteCustom ? selectionQuery(applied, def) : null;

  useEffect(() => {
    if (!def || query === null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get<ReportData>(`/api/reports/${encodeURIComponent(id)}/data${query}`)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setDataQuery(query);
        setLoading(false);
        setShownAt(new Date());
      })
      .catch((e) => {
        if (cancelled) return;
        setData(null);
        setDataQuery(null);
        setError(e instanceof ApiError ? e.message : t.common.unexpected);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [def, id, query]);

  const fresh = data !== null && dataQuery === query;
  queryRef.current = query;
  versionRef.current = fresh && data ? data.freshness.data_version : null;
  loadingRef.current = loading;

  const apply = useCallback(
    (s: ReportSelection) => {
      if (!def || !applied || sameSelection(s, applied)) return;
      // The selection is rewritten from scratch; the reader's own view keys must survive it.
      const next = serializeSelection(s, def);
      for (const [key, value] of Object.entries(parseViewState(params))) {
        if (value !== null) next.set(key, value);
      }
      setParams(next, { replace: true });
    },
    [def, applied, params, setParams],
  );

  /** Feature 053: a parameter chip restores that parameter's default (and its URL key). */
  const removeParameterChip = useCallback(
    (chip: ParameterChip) => {
      if (!def || !applied) return;
      if (chip.key === "period") {
        apply({ ...applied, period: def.periods.default, from: "", to: "" });
      } else if (chip.key === "compare") {
        apply({ ...applied, compare: def.compare.default });
      } else if (chip.key === "theme") {
        setView({ theme: null });
      } else {
        setView({ mode: null });
      }
    },
    [applied, apply, def, setView],
  );

  /** The Parámetros tab's Limpiar: the report's defaults and the reader's own view, in one write so
   * the two updates cannot overwrite each other. */
  const clearAll = useCallback(() => {
    if (!def || !applied) return;
    writeViewerMode(id, null);
    setParams(serializeSelection(defaultSelection(def), def), { replace: true });
  }, [applied, def, id, setParams]);

  const refreshData = useCallback(async (): Promise<boolean> => {
    const q = queryRef.current;
    if (q === null || loadingRef.current) return false;
    const y = window.scrollY;
    const d = await api.get<ReportData>(`/api/reports/${encodeURIComponent(id)}/data${q}`);
    if (queryRef.current !== q) return false;
    const changed = d.freshness.data_version !== versionRef.current;
    setData(d);
    setDataQuery(q);
    setError(null);
    const now = new Date();
    setShownAt(now);
    if (changed) toast(liveT.autoRefresh.updated(formatClock(now))); // live binding: a language switch must not restart auto-refresh
    requestAnimationFrame(() => {
      if (Math.abs(window.scrollY - y) > 1) window.scrollTo(0, y);
    });
    return true;
  }, [id, toast]);

  const effectiveMode =
    tv && storedMode === "off" ? ("data" as const) : storedMode;

  const { status: autoStatus } = useAutoRefresh({
    reportId: id,
    mode: def ? effectiveMode : "off",
    currentVersion: fresh && data ? data.freshness.data_version : null,
    onRefresh: refreshData,
  });

  const exitTv = useCallback(() => {
    enteredFsRef.current = false;
    void exitFullscreen();
    const next = new URLSearchParams(params);
    next.delete("tv");
    setParams(next, { replace: true });
  }, [params, setParams]);

  exitTvRef.current = exitTv;

  const enterTv = useCallback(() => {
    const next = new URLSearchParams(params);
    next.set("tv", "1");
    setParams(next, { replace: true });
    void enterFullscreen().then((ok) => {
      enteredFsRef.current = ok;
    });
  }, [params, setParams]);

  const onFullscreen = useCallback(() => {
    void enterFullscreen().then((ok) => {
      enteredFsRef.current = ok;
    });
  }, []);

  const loadOptions = useCallback(
    (filterId: string, base: ReportSelection, q: string) =>
      api.get<MultiSelectOptions>(
        `/api/reports/${encodeURIComponent(id)}/filters/${encodeURIComponent(filterId)}${filterOptionsQuery(base, q)}`,
      ),
    [id],
  );

  const exportPdf = useCallback(() => {
    if (query === null) return;
    setPdfBusy(true);
    setPdfError(null);
    const range = fresh && data ? data.selection.current : null;
    const filename = `${id}${range ? `-${range.from}-${range.to}` : ""}.pdf`;
    downloadPdf(id, query, filename, t.reportParams.pdfError)
      .catch((e: Error) => setPdfError(e.message))
      .finally(() => setPdfBusy(false));
  }, [data, fresh, id, query, t]);

  const exportCsv = useCallback(() => {
    if (!fresh || !data) return;
    const tables: CsvTable[] = data.views
      .map((v) => viewCsvTable(v))
      .filter((table): table is CsvTable => table !== null);
    if (tables.length === 0) return;
    const range = data.selection.current;
    const filename = csvFileName(`${id}-${range.from}-${range.to}`);
    const text =
      tables.length === 1
        ? toCsv(tables[0].columns, tables[0].rows)
        : toCsvSections(tables);
    downloadCsv(filename, text);
  }, [data, fresh, id]);

  const csvBase = fresh && data
    ? `${id}-${data.selection.current.from}-${data.selection.current.to}`
    : undefined;

  const ready = fresh && !loading;
  const csvAvailable = fresh && !!data?.views.some(
    (v) => !v.error && !v.empty && (v.type === "table" || v.type === "ranking"),
  );

  const activeCount = useMemo(() => {
    if (!applied || !def) return 0;
    return def.filters.reduce(
      (sum, f) => sum + (applied.filters[f]?.length ?? 0),
      0,
    );
  }, [applied, def]);

  // Feature 026: a layout's `filters` component reuses this screen's filter state, so the layout
  // never grows a second one.
  const layoutParams = useMemo<LayoutParamsWiring | undefined>(
    () => (applied ? { applied, onApply: apply, loadOptions } : undefined),
    [applied, apply, loadOptions],
  );

  // Feature 063: one click either replaces the dimension's value, removes it, or adds to it.
  const crossFilter = useMemo<CrossFilterState | undefined>(() => {
    if (!def || !applied) return undefined;
    return {
      enabled: def.interactions?.cross_filter !== false,
      filters: applied.filters,
      toggle: (dimension, value, additive) => {
        const current = applied.filters[dimension] ?? [];
        let values: string[];
        if (additive) {
          values = current.includes(value)
            ? current.filter((entry) => entry !== value)
            : [...current, value];
        } else {
          values = current.length === 1 && current[0] === value ? [] : [value];
        }
        const filters = { ...applied.filters };
        if (values.length > 0) filters[dimension] = values;
        else delete filters[dimension];
        apply({ ...applied, filters });
      },
    };
  }, [applied, apply, def]);

  const renderViews = useCallback(
    (kpiSize: "normal" | "tv") => {
      if (!data) return null;
      return (
        <ReportViews data={data} def={def!} kpiSize={kpiSize}
          csvBase={kpiSize === "normal" ? csvBase : undefined}
          params={layoutParams}
          crossFilter={crossFilter}
          onMaximize={maximize} />
      );
    },
    [data, def, csvBase, layoutParams, crossFilter, maximize],
  );

  if (!def) {
    return (
      <div>
        <Breadcrumbs back="/" items={[]} />
        {error ? (
          <Alert tone="error">{error}</Alert>
        ) : (
          <div role="status" className="flex justify-center py-12 text-accent">
            <Spinner className="h-8 w-8" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        )}
      </div>
    );
  }

  if (tv && applied) {
    return (
      <TvLayout
        title={localized(def, "title")}
        periodText={t.reportParams.periodLabels[applied.period] ?? applied.period}
        rangeText={fresh && data ? formatRange(data.selection.current) : null}
        updatedText={freshnessText(data, def)}
        status={<AutoRefreshStatusLine status={autoStatus} lastAt={shownAt} />}
        fullscreenAvailable={fullscreenSupported()}
        fullscreen={fs}
        onFullscreen={onFullscreen}
        onExit={exitTv}
      >
        {error ? <Alert tone="error">{error}</Alert> : null}

        {fresh && data && isStale(data) ? (
          <Alert tone="warning">{staleText(data)}</Alert>
        ) : null}

        {loading && !data ? (
          <div role="status" className="flex justify-center py-12 text-accent">
            <Spinner className="h-8 w-8" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        ) : null}

        {data ? (
          <ReportArea
            theme={tokens}
            mode={areaMode}
            className={`space-y-6 transition-opacity motion-reduce:transition-none ${loading || !fresh ? "opacity-60" : ""}`}
            aria-busy={loading || undefined}
            inert={!fresh || loading ? true : undefined}
          >
            {renderViews("tv")}
          </ReportArea>
        ) : null}
      </TvLayout>
    );
  }

  return (
    <div>
      <Breadcrumbs
        back="/"
        items={[
          { label: t.nav.home, to: "/" },
          { label: localized(def, "title") },
        ]}
      />

      <PageHeader
        title={localized(def, "title")}
        subtitle={localized(def, "description") || undefined}
        actions={
          applied ? (
            <ReportActions
              activeFilters={activeCount}
              onOpenFilters={openFilters}
              onOpenParams={toggleParams}
              caption={ready ? t.reportParams.exportCaptionApplied : t.reportParams.exportCaptionLoading}
              actions={[
                {
                  id: "pdf",
                  label: t.reportActions.pdf,
                  icon: FileDown,
                  onClick: exportPdf,
                  show: def.pdf && query !== null,
                  loading: pdfBusy,
                },
                {
                  id: "csv",
                  label: t.reportActions.csv,
                  icon: FileDown,
                  onClick: exportCsv,
                  show: csvAvailable,
                },
                {
                  id: "share",
                  label: t.reportActions.share,
                  icon: Share2,
                  onClick: () => setSharePanel("share"),
                  show: user?.role === "admin" && !!dashCode,
                },
                {
                  id: "email",
                  label: t.reportActions.email,
                  icon: Mail,
                  onClick: () => setSharePanel("email"),
                  show: !!dashCode && emailAvailable,
                },
                {
                  id: "sends",
                  label: t.reportActions.sends,
                  icon: History,
                  onClick: () => setSharePanel("sends"),
                  show: !!dashCode && emailAvailable,
                },
                {
                  id: "schedules",
                  label: t.reportActions.schedules,
                  icon: CalendarClock,
                  onClick: () => setSharePanel("schedules"),
                  show: user?.role === "admin" && !!dashCode,
                },
                {
                  id: "mode",
                  label: areaMode === "dark" ? t.reportActions.modeLight : t.reportActions.modeDark,
                  icon: areaMode === "dark" ? Sun : Moon,
                  onClick: toggleMode,
                  show: true,
                },
                {
                  id: "tv",
                  label: t.reportActions.tv,
                  icon: Tv,
                  onClick: enterTv,
                  show: true,
                },
              ]}
            />
          ) : undefined
        }
      />

      {applied ? (
        <div className="mb-5">
          <ReportMetaLine
            def={def}
            applied={applied}
            data={fresh ? data : null}
            onRemoveFilter={(filterId, value) => apply(withoutFilterValue(applied, filterId, value))}
            onRemoveAllFilters={(filterId) => {
              const filters = { ...applied.filters };
              delete filters[filterId];
              apply({ ...applied, filters });
            }}
            onOpenFilters={openFilters}
            view={{
              theme: viewState.theme,
              mode: viewState.mode,
              declaredTheme: declaredPalette,
              onRemove: removeParameterChip,
            }}
          />
        </div>
      ) : null}

      {/* The report's own area paints from its theme and its mode: with `mode: dark` inside a
          light application the chrome stays as the viewer chose and only this block turns. */}
      <ReportArea theme={tokens} mode={areaMode} className="mt-5 min-w-0 space-y-5">
          <AutoRefreshStatusLine status={autoStatus} lastAt={shownAt} />

          {pdfError ? <Alert tone="error">{pdfError}</Alert> : null}

          {error ? <Alert tone="error">{error}</Alert> : null}

          {fresh && data && isStale(data) ? (
            <Alert tone="warning">{staleText(data)}</Alert>
          ) : null}

          {loading && !data ? (
            <div
              role="status"
              className="flex justify-center py-12 text-accent"
            >
              <Spinner className="h-8 w-8" />
              <span className="sr-only">{t.common.loading}</span>
            </div>
          ) : null}

          {data ? (
            <div
              className={`space-y-5 transition-opacity motion-reduce:transition-none ${loading || !fresh ? "opacity-60" : ""}`}
              aria-busy={loading || undefined}
              inert={!fresh || loading ? true : undefined}
            >
              {renderViews("normal")}
            </div>
          ) : null}
      </ReportArea>

      {/* Feature 056: the maximised card, rendered from the same tree so it cannot drift. */}
      {maximizedId && data && def ? (
        <MaximizedCard
          id={maximizedId}
          data={data}
          def={def}
          csvBase={csvBase}
          params={layoutParams}
          crossFilter={crossFilter}
          onMaximize={maximize}
          onClose={closeMaximized}
        />
      ) : null}

      <ReportSheet
        open={panel !== null}
        title={t.reportActions.filters(activeCount)}
        onClose={closePanel}
        tabs={[
          { id: "filters", label: t.reportSheet.tabs.filters },
          { id: "params", label: t.reportSheet.tabs.params },
        ]}
        tab={panel ?? "filters"}
        onTabChange={(id) => setPanel(id as "filters" | "params")}
        footer={
          <div className="flex gap-2">
            <Button variant="ghost" block onClick={clearAll}>
              {t.reportSheet.clear}
            </Button>
            <Button variant="primary" block onClick={closePanel}>
              {t.reportSheet.done}
            </Button>
          </div>
        }
      >
        {applied && panel === "filters" ? (
          <ParamsForm
            def={def}
            applied={applied}
            onApply={apply}
            loadOptions={loadOptions}
            live
            section="filters"
            className="space-y-5"
          >
            {unknownFilters.length > 0 ? (
              <Alert tone="info">{t.reportSheet.unknownFilter}</Alert>
            ) : null}
          </ParamsForm>
        ) : null}
        {applied && panel === "params" ? (
          <ReportParamsPanel
            def={def}
            applied={applied}
            onApply={apply}
            loadOptions={loadOptions}
            refresh={{
              mode: storedMode,
              onChange: setStoredMode,
              cacheSeconds: def.direct?.cache_seconds,
            }}
            palette={{
              value: viewState.theme,
              onChange: (preset) => setView({ theme: preset }),
            }}
            themeMode={
              declaredTheme
                ? { value: viewState.mode, onChange: (mode) => setView({ mode }) }
                : undefined
            }
            mode={areaMode}
          />
        ) : null}
      </ReportSheet>

      <View
        open={sharePanel === "share"}
        title={t.sharing.shareTitle}
        onClose={() => setSharePanel(null)}
      >
        {sharePanel === "share" && dashCode ? (
          <ShareLinksPanel code={dashCode} />
        ) : null}
      </View>

      <View
        open={sharePanel === "email"}
        title={t.sharing.email.emailTitle}
        onClose={() => setSharePanel(null)}
      >
        {sharePanel === "email" && dashCode ? (
          <EmailSendPanel
            code={dashCode}
            dashboardName={localized(def, "title")}
            selection={applied}
            pdfAvailable={!!def.pdf}
            isAdmin={user?.role === "admin"}
          />
        ) : null}
      </View>

      <View
        open={sharePanel === "sends"}
        title={t.sharing.email.sends}
        onClose={() => setSharePanel(null)}
      >
        {sharePanel === "sends" && dashCode ? <SendHistoryPanel code={dashCode} /> : null}
      </View>

      <View
        open={sharePanel === "schedules"}
        title={t.sharing.schedules.schedulesTitle}
        onClose={() => setSharePanel(null)}
      >
        {sharePanel === "schedules" && dashCode ? (
          <SubscriptionsPanel code={dashCode} def={def} />
        ) : null}
      </View>
    </div>
  );
}

/** The view a maximised card draws, whichever kind of card it is. */
function maximizedView(id: string, data: ReportData, def: ReportDefinition) {
  if (id.startsWith(VIEW_CARD_PREFIX)) return data.views[Number(id.slice(VIEW_CARD_PREFIX.length))];
  const component = (def.layout?.web?.components ?? []).find((entry) => entry.id === id);
  return component?.view ? data.views.find((view) => view.id === component.view) : undefined;
}

/**
 * Feature 056: one card at the viewport's size.
 *
 * The same tree is rendered again (a layout component through `LayoutRenderer`, a default view
 * through `SingleView`), so a maximised card cannot show something the dashboard does not. The
 * arrows walk the dashboard's cards; the CSV is the view's own export; the PNG is the drawing.
 */
function MaximizedCard({ id, data, def, csvBase, params, crossFilter, onMaximize, onClose }: {
  id: string;
  data: ReportData;
  def: ReportDefinition;
  csvBase?: string;
  params?: LayoutParamsWiring;
  crossFilter?: CrossFilterState;
  onMaximize: (id: string, replace?: boolean) => void;
  onClose: () => void;
}) {
  const t = useT();
  const frame = useRef<HTMLDivElement>(null);
  const byView = id.startsWith(VIEW_CARD_PREFIX);
  const index = byView ? Number(id.slice(VIEW_CARD_PREFIX.length)) : -1;
  const component = byView
    ? undefined
    : (def.layout?.web?.components ?? []).find((entry) => entry.id === id);
  const cards = byView
    ? data.views.map((_, position) => `${VIEW_CARD_PREFIX}${position}`)
    : (def.layout?.web?.components ?? [])
        .filter((entry) => entry.type !== "text" && entry.type !== "filters"
          && entry.type !== "spacer")
        .map((entry) => entry.id);
  const position = cards.indexOf(id);
  const view = maximizedView(id, data, def);
  const table = view ? viewCsvTable(view) : null;
  const title = byView
    ? (view && "title" in view ? localized(view as { title?: string }, "title") : undefined)
      ?? t.reportParams.detailTitle
    : (cardTitle(def, id, view as { title?: string } | undefined) ?? t.reportParams.detailTitle);

  // Feature 056b: moving between cards replaces the history entry, so Back closes the dialog
  // instead of stepping through it.
  const go = (step: -1 | 1) => {
    const target = cards[position + step];
    if (target) onMaximize(target, true);
  };

  return (
    <CardDialog
      open
      title={title}
      onClose={onClose}
      onPrevious={position > 0 ? () => go(-1) : undefined}
      onNext={position >= 0 && position < cards.length - 1 ? () => go(1) : undefined}
      onDownloadPng={() => downloadCardPng(frame.current, title)}
      onDownloadCsv={table
        ? () => downloadCsv(
            csvBase ? csvFileName(`${csvBase}-${table.title}`) : csvFileName(table.title),
            toCsv(table.columns, table.rows))
        : undefined}
      period={t.reportParams.periodLabels[data.selection.period] ?? data.selection.period}
      comparison={data.selection.previous && data.selection.compare !== "none"
        ? t.reportParams.compareLabels[data.selection.compare] : undefined}
      filters={Object.entries(data.filters ?? {})
        .flatMap(([field, values]) => values.map((value) => `${field}: ${value}`))}
    >
      {/* Feature 056b: the frame is the height the chart measures, and the card is told it is the
          dialog's: one card across the whole width, no own title, no menu. */}
      <div ref={frame} className="flex h-full min-h-0 flex-col">
        {byView ? (
          <SingleView index={index} data={data} def={def} csvBase={csvBase} params={params}
                      crossFilter={crossFilter} />
        ) : def.layout?.web && component ? (
          <LayoutRenderer
            layout={{ ...def.layout.web, gutter: "md", components: [{ ...component, span: 12 }] }}
            data={data}
            def={def}
            csvBase={csvBase}
            params={params}
            crossFilter={crossFilter}
            fill
            maximized
          />
        ) : null}
      </div>
    </CardDialog>
  );
}
