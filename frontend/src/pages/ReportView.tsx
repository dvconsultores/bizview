import {
  CalendarClock,
  FileDown,
  Mail,
  PanelLeftOpen,
  Share2,
  SlidersHorizontal,
  Tv,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router";
import { api, ApiError } from "../api/client";
import type {
  Dashboard,
  EmailOptions,
  ReportData,
  ReportDefinition,
} from "../api/types";
import { Alert } from "../components/Alert";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Narrative } from "../components/report/Narrative";
import { ReportViews } from "../components/report/ReportViews";
import type { LayoutParamsWiring } from "../components/report/LayoutBlocks";
import { Spinner } from "../components/Spinner";
import { ContextBlock } from "../components/report/ContextBlock";
import {
  ParamsPanel,
  useReportPanelCollapsed,
} from "../components/report/ParamsPanel";
import { ParamsForm } from "../components/report/ParamsForm";
import { ExportSection } from "../components/report/ExportSection";
import { View } from "../components/View";
import type { MultiSelectOptions } from "../components/MultiSelect";
import { useAuth } from "../auth/AuthContext";
import { recordRecent } from "../lib/dashboardPrefs";
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
  filterOptionsQuery,
  isIncompleteCustom,
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
import { AutoRefreshControl, AutoRefreshStatusLine } from "../components/report/AutoRefreshControl";
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
import { EmailSendPanel } from "../components/sharing/EmailSendPanel";
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
  const location = useLocation();
  const [def, setDef] = useState<ReportDefinition | null>(null);
  const [data, setData] = useState<ReportData | null>(null);
  const [dataQuery, setDataQuery] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useReportPanelCollapsed();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [pendingApply, setPendingApply] = useState<ReportSelection | null>(null);
  const [shownAt, setShownAt] = useState<Date | null>(null);
  const [storedMode, setStoredMode] = useAutoRefreshMode(id);
  const [fs, setFs] = useState(() => isFullscreen());
  const enteredFsRef = useRef(false);
  const exitTvRef = useRef<() => void>(() => undefined);

  const queryRef = useRef<string | null>(null);
  const versionRef = useRef<string | null>(null);
  const loadingRef = useRef(false);

  const tv = params.get("tv") === "1";

  // TV mode is meant to be looked at, not worked in: the chat steps aside with the rest of the
  // chrome (feature 025).
  useHideShellChrome(tv, false);

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
    "share" | "email" | "schedules" | null
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
      setParams(serializeSelection(s, def), { replace: true });
    },
    [def, applied, setParams],
  );

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
  const pdfAvailable = !!def?.pdf;
  const csvAvailable = fresh && !!data?.views.some(
    (v) => v.type === "table" || v.type === "ranking",
  );

  const exportSection = (
    <ExportSection
      pdfAvailable={pdfAvailable}
      csvAvailable={csvAvailable}
      ready={ready}
      pdfBusy={pdfBusy}
      onPdf={exportPdf}
      onCsv={exportCsv}
    />
  );

  const applyFromView = useCallback(
    (s: ReportSelection) => {
      setFiltersOpen(false);
      if (applied && !sameSelection(s, applied)) {
        setPendingApply(s);
      }
    },
    [applied],
  );

  // Apply a selection chosen in the phone view only after the view's history entry is popped,
  // otherwise the replace would land on the view entry and the pop would restore the old URL.
  useEffect(() => {
    if (
      pendingApply !== null &&
      !((location.state as { view?: string[] } | null)?.view?.length)
    ) {
      apply(pendingApply);
      setPendingApply(null);
    }
  }, [pendingApply, location.state, apply]);

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

  const renderViews = useCallback(
    (kpiSize: "normal" | "tv") => {
      if (!data) return null;
      return (
        <ReportViews data={data} def={def!} kpiSize={kpiSize}
          csvBase={kpiSize === "normal" ? csvBase : undefined}
          params={layoutParams} />
      );
    },
    [data, def, csvBase, layoutParams],
  );

  if (!def) {
    return (
      <div className="mx-auto max-w-7xl">
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
          <div
            className={`space-y-6 transition-opacity motion-reduce:transition-none ${loading || !fresh ? "opacity-60" : ""}`}
            aria-busy={loading || undefined}
            inert={!fresh || loading ? true : undefined}
          >
            {renderViews("tv")}
          </div>
        ) : null}
      </TvLayout>
    );
  }

  return (
    <div className="mx-auto max-w-7xl">
      <Breadcrumbs
        back="/"
        items={[
          { label: t.nav.home, to: "/" },
          { label: localized(def, "title") },
        ]}
      />
      <PageHeader title={localized(def, "title")} subtitle={localized(def, "description") || undefined} />

      <div
        className={
          collapsed
            ? "space-y-5"
            : "lg:grid lg:grid-cols-[20rem_minmax(0,1fr)] lg:items-start lg:gap-6"
        }
      >
        {!collapsed && applied ? (
          <ParamsPanel onCollapse={() => setCollapsed(true)}>
            <ParamsForm
              def={def}
              applied={applied}
              onApply={apply}
              loadOptions={loadOptions}
            >
              <AutoRefreshControl
              mode={storedMode}
              onChange={setStoredMode}
              cacheSeconds={def.direct?.cache_seconds}
            />
              {exportSection}
            </ParamsForm>
          </ParamsPanel>
        ) : null}

        <div className="min-w-0 space-y-5">
          {applied ? (
            <ContextBlock
              def={def}
              applied={applied}
              data={fresh ? data : null}
              viewer={user?.full_name ?? null}
              incompleteCustom={incompleteCustom}
              onRemoveFilter={(filterId, value) =>
                apply(withoutFilterValue(applied, filterId, value))
              }
              actions={
                <>
                  <Button
                    variant="secondary"
                    className="lg:hidden"
                    icon={<SlidersHorizontal className="h-5 w-5" aria-hidden />}
                    onClick={() => setFiltersOpen(true)}
                  >
                    {t.reportParams.filtersButton(activeCount)}
                  </Button>
                  {collapsed ? (
                    <Button
                      variant="secondary"
                      className="hidden lg:inline-flex"
                      icon={<PanelLeftOpen className="h-5 w-5" aria-hidden />}
                      onClick={() => setCollapsed(false)}
                    >
                      {t.reportParams.expand}
                    </Button>
                  ) : null}
                  <Button
                    variant="secondary"
                    icon={<Tv className="h-5 w-5" aria-hidden />}
                    onClick={enterTv}
                  >
                    {t.tvMode.enter}
                  </Button>
                  {def.pdf && query !== null ? (
                    <Button
                      variant="secondary"
                      loading={pdfBusy}
                      icon={<FileDown className="h-5 w-5" aria-hidden />}
                      onClick={exportPdf}
                    >
                      {t.reportParams.downloadPdf}
                    </Button>
                  ) : null}
                  {user?.role === "admin" && dashCode ? (
                    <Button
                      variant="secondary"
                      icon={<Share2 className="h-5 w-5" aria-hidden />}
                      onClick={() => setSharePanel("share")}
                    >
                      {t.sharing.share}
                    </Button>
                  ) : null}
                  {dashCode && emailAvailable ? (
                    <Button
                      variant="secondary"
                      icon={<Mail className="h-5 w-5" aria-hidden />}
                      onClick={() => setSharePanel("email")}
                    >
                      {t.sharing.email.emailButton}
                    </Button>
                  ) : null}
                  {user?.role === "admin" && dashCode ? (
                    <Button
                      variant="secondary"
                      icon={
                        <CalendarClock className="h-5 w-5" aria-hidden />
                      }
                      onClick={() => setSharePanel("schedules")}
                    >
                      {t.sharing.schedules.schedulesButton}
                    </Button>
                  ) : null}
                </>
              }
            />
          ) : null}

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
              {def.ai_narrative && query !== null ? (
                <Narrative reportId={id} query={query} />
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <View
        open={filtersOpen}
        title={t.reportParams.panelTitle}
        onClose={() => setFiltersOpen(false)}
      >
        {filtersOpen && applied ? (
          <ParamsForm
            def={def}
            applied={applied}
            onApply={applyFromView}
            loadOptions={loadOptions}
          >
            <AutoRefreshControl
              mode={storedMode}
              onChange={setStoredMode}
              cacheSeconds={def.direct?.cache_seconds}
            />
            {exportSection}
          </ParamsForm>
        ) : null}
      </View>

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
          />
        ) : null}
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
