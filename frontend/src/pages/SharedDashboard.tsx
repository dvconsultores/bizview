import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { FileDown, Link2Off, RefreshCw } from "lucide-react";
import { api, ApiError } from "../api/client";
import type {
  ReportData,
  ReportDefinition,
  SharedDashboard as SharedDashboardData,
} from "../api/types";
import { ParamsForm } from "../components/report/ParamsForm";
import { ReportActions } from "../components/report/ReportActions";
import { ReportMetaLine } from "../components/report/ReportMetaLine";
import { ReportParamsPanel } from "../components/report/ReportParamsPanel";
import { ReportSheet } from "../components/report/ReportSheet";
import { ReportArea } from "../components/report/ReportArea";
import { ReportViews, VIEW_CARD_PREFIX } from "../components/report/ReportViews";
import { CardDialog } from "../components/report/CardDialog";
import { CardDataTable } from "../components/report/CardDataTable";
import { componentView } from "../components/report/LayoutRenderer";
import type { MultiSelectOptions } from "../components/MultiSelect";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { ThemeSwitcher } from "../components/ThemeSwitcher";
import { Logo } from "../components/Logo";
import { LegalLinks } from "../components/LegalLinks";
import { useBranding } from "../config/BrandingContext";
import { readViewerMode, reportMode } from "../theme/library";
import type { ThemeMode } from "../theme/themes";
import { useT } from "../i18n";
import { localized } from "../lib/labels";
import { cardTitle } from "../lib/cardTitle";
import { downloadPdf } from "../lib/download";
import { formatDate } from "../lib/format";
import { isStale, staleText } from "../lib/freshness";
import {
  defaultSelection,
  filterOptionsQuery,
  isIncompleteCustom,
  parseSelection,
  sameSelection,
  selectionQuery,
  serializeSelection,
  withoutFilterValue,
} from "../lib/reportQuery";
import type { ReportSelection } from "../lib/reportQuery";
import { parseViewState, togglePanel } from "../lib/reportView";
import { errorText } from "../lib/sharing";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { readCachedPreference } from "../theme/resolve";
import { useTheme } from "../theme/ThemeContext";
import { PageContainer } from "../components/PageContainer";
import { Spinner } from "../components/Spinner";

type LoadState =
  | { status: "loading" }
  | { status: "expired" }
  | { status: "throttled" }
  | { status: "error"; message: string }
  | { status: "ok"; shared: SharedDashboardData };

/** Feature 064: the view, component and title behind a `?tabla=` id on a shared report. */
function sharedTableEntry(id: string, data: ReportData, report: ReportDefinition) {
  if (report.interactions?.data_table === false) return null;
  if (id.startsWith(VIEW_CARD_PREFIX)) {
    const view = data.views[Number(id.slice(VIEW_CARD_PREFIX.length))];
    if (!view || view.error || view.empty) return null;
    const title = ("title" in view && localized(view as { title?: string }, "title"))
      || (view.type === "ranking" ? localized(view, "label") : undefined)
      || localized(report, "title");
    return { view, title };
  }
  const component = (report.layout?.web?.components ?? []).find((entry) => entry.id === id);
  if (!component || component.data_table === false) return null;
  const base = component.view ? data.views.find((view) => view.id === component.view) : undefined;
  if (!base || base.error || base.empty) return null;
  return {
    view: componentView(component, base, data),
    component,
    title: cardTitle(report, id, base as { title?: string }) ?? localized(report, "title"),
  };
}

/** Public, read-only view of one dashboard through an expiring share link (feature 018). */
export function SharedDashboard() {
  const t = useT();
  const { token = "" } = useParams();
  const base = `/api/shared/${encodeURIComponent(token)}`;
  const [params, setParams] = useSearchParams();
  const tableId = params.get("tabla");
  const openTable = (id: string) => {
    const next = new URLSearchParams(params);
    next.set("tabla", id);
    setParams(next, { replace: true });
  };
  const closeTable = () => {
    const next = new URLSearchParams(params);
    next.delete("tabla");
    setParams(next, { replace: true });
  };
  const branding = useBranding();

  const [sharedState, setSharedState] = useState<LoadState>({
    status: "loading",
  });
  const [data, setData] = useState<ReportData | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataQuery, setDataQuery] = useState<string | null>(null);
  // Feature 053: one sheet with two tabs, exactly as the private report page.
  const [panel, setPanel] = useState<"filters" | "params" | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const previousTitleRef = useRef<string>(document.title);
  const { setPalette, setPreference, tokens, resolved } = useTheme();
  const linkThemeApplied = useRef(false);

  // Feature 030 (contracts/share-theme.md): the sharer's theme applies on the first load only, and
  // only when this browser has no stored preference; afterwards the viewer's choice wins.
  useEffect(() => {
    if (sharedState.status !== "ok" || linkThemeApplied.current) return;
    linkThemeApplied.current = true;
    const forced = sharedState.shared.theme;
    if (forced && readCachedPreference() === "system") void setPreference(forced);
  }, [sharedState, setPreference]);

  const report = useMemo<ReportDefinition | null>(
    () =>
      sharedState.status === "ok" ? sharedState.shared.report : null,
    [sharedState],
  );

  const applied = useMemo(
    () => (report ? parseSelection(params, report) : null),
    [params, report],
  );

  // Feature 030/047: the report's declared theme wins over the installation's in the shared view
  // too, and the link opens in the report's own mode before the viewer chooses (FR-020).
  const link = report?.layout?.theme;
  useEffect(() => {
    if (!report) return;
    setPalette(link?.id ?? link?.palette ?? null);
  }, [report, link, setPalette]);
  useEffect(() => () => setPalette(null), [setPalette]);
  const linkMode = reportMode(link);
  // A viewer who already toggled this report keeps that choice for the session (FR-019).
  const viewerMode = readViewerMode(report?.id ?? "");
  const areaMode: ThemeMode = viewerMode ?? (linkMode === "auto" ? resolved : linkMode);

  /** The Parámetros tab's Limpiar: the report's defaults (the share link has no palette/mode). */
  const clearAll = () => {
    if (!applied || !report) return;
    setParams(serializeSelection(defaultSelection(report), report), { replace: true });
  };

  const activeCount = useMemo(() => {
    if (!applied || !report) return 0;
    return report.filters.reduce((sum, id) => sum + (applied.filters[id]?.length ?? 0), 0);
  }, [applied, report]);

  const apply = useCallback(
    (s: ReportSelection) => {
      if (!report || !applied || sameSelection(s, applied)) {
        return;
      }
      const next = serializeSelection(s, report);
      for (const [key, value] of Object.entries(parseViewState(params))) {
        if (value !== null) next.set(key, value);
      }
      setParams(next, { replace: true });
    },
    [report, applied, params, setParams],
  );

  const loadOptions = useCallback(
    (filterId: string, baseSelection: ReportSelection, q: string) =>
      api.get<MultiSelectOptions>(
        `${base}/filters/${encodeURIComponent(filterId)}${filterOptionsQuery(baseSelection, q)}`,
      ),
    [base],
  );

  const loadShared = useCallback(async () => {
    setSharedState({ status: "loading" });
    setDataError(null);
    try {
      const shared = await api.get<SharedDashboardData>(base);
      setSharedState({ status: "ok", shared });
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 429) {
          setSharedState({ status: "throttled" });
          return;
        }
        if (e.status >= 400 && e.status < 500) {
          setSharedState({ status: "expired" });
          return;
        }
      }
      setSharedState({ status: "error", message: errorText(e) });
    }
  }, [base]);

  useEffect(() => {
    void loadShared();
    const robots = document.createElement("meta");
    robots.name = "robots";
    robots.content = "noindex, nofollow";
    const referrer = document.createElement("meta");
    referrer.name = "referrer";
    referrer.content = "no-referrer";
    document.head.appendChild(robots);
    document.head.appendChild(referrer);
    return () => {
      document.head.removeChild(robots);
      document.head.removeChild(referrer);
      document.title = previousTitleRef.current;
    };
  }, [loadShared]);

  useEffect(() => {
    if (sharedState.status === "ok") {
      document.title = localized(sharedState.shared.dashboard, "name");
    }
  }, [sharedState]);

  const incompleteCustom = applied ? isIncompleteCustom(applied) : false;
  const query =
    applied && report && !incompleteCustom
      ? selectionQuery(applied, report)
      : null;

  useEffect(() => {
    if (!report || query === null) {
      return;
    }
    let cancelled = false;
    setDataLoading(true);
    setDataError(null);
    setPdfError(null);
    api
      .get<ReportData>(`${base}/data${query}`)
      .then((reportData) => {
        if (cancelled) return;
        setData(reportData);
        setDataQuery(query);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setSharedState({ status: "expired" });
        } else {
          setDataError(errorText(e));
        }
      })
      .finally(() => {
        if (!cancelled) setDataLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [base, report, query]);

  const fresh = data !== null && dataQuery === query;
  const tableCard = tableId && data && report ? sharedTableEntry(tableId, data, report) : null;

  const handlePdf = async () => {
    if (!report || !query) return;
    setPdfBusy(true);
    setPdfError(null);
    try {
      const filename = fresh
        ? `${report.id}-${data?.selection.current.from ?? ""}-${data?.selection.current.to ?? ""}.pdf`
        : `${report.id}.pdf`;
      await downloadPdf(`${base}/pdf${query}`, filename, t.reportParams.pdfError);
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : t.reportParams.pdfError);
    } finally {
      setPdfBusy(false);
    }
  };

  if (sharedState.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div role="status" className="flex justify-center py-8 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      </div>
    );
  }

  if (sharedState.status === "expired") {
    return (
      <main className="flex min-h-screen items-center justify-center px-4 py-12">
        <Card className="w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-2 text-ink-muted">
            <Link2Off className="h-8 w-8" aria-hidden />
          </div>
          <h1 className="text-2xl font-bold text-ink">
            {t.sharing.shared.expiredTitle}
          </h1>
          <p className="mt-3 text-sm text-ink-2">
            {t.sharing.shared.expiredText}
          </p>
        </Card>
      </main>
    );
  }

  if (sharedState.status === "throttled") {
    return (
      <main className="flex min-h-screen items-center justify-center px-4 py-12">
        <Card className="w-full max-w-lg p-8 text-center">
          <h1 className="text-2xl font-bold text-ink">
            {t.sharing.shared.tooManyTitle}
          </h1>
          <p className="mt-3 text-sm text-ink-2">
            {t.sharing.shared.tooManyText}
          </p>
          <div className="mt-6">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-5 w-5" aria-hidden />}
              onClick={() => void loadShared()}
            >
              {t.common.retry}
            </Button>
          </div>
        </Card>
      </main>
    );
  }

  if (sharedState.status === "error" || !report) {
    return (
      <PageContainer as="main" className="py-12">
        <Alert
          tone="error"
          action={
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-5 w-5" aria-hidden />}
              onClick={() => void loadShared()}
            >
              {t.common.retry}
            </Button>
          }
        >
          {sharedState.status === "error"
            ? sharedState.message
            : t.common.unexpected}
        </Alert>
      </PageContainer>
    );
  }

  const sharedData = sharedState.shared;
  const orgName = branding.organization_name || branding.product_name;

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <PageContainer className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
          <Logo className="h-8 w-8 shrink-0" />
          <span className="min-w-0 flex-1 truncate font-semibold text-ink">{orgName}</span>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <LanguageSwitcher compact />
            {/* Feature 030 (FR-006): the viewer picks the theme; the choice stays on this device. */}
            <ThemeSwitcher compact />
          </div>
        </PageContainer>
      </header>

      <PageContainer as="main" className="py-6">
        <div className="space-y-5">
          <Alert tone="info">
            {t.sharing.shared.banner(formatDate(sharedData.expires_at))}
          </Alert>

          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-bold text-ink sm:text-3xl">
                {localized(sharedData.dashboard, "name")}
              </h1>
              {localized(report, "description") && (
                <p className="mt-1 text-sm text-ink-2">{localized(report, "description")}</p>
              )}
              {applied ? (
                <div className="mt-2">
                  <ReportMetaLine
                    def={report}
                    applied={applied}
                    data={fresh ? data : null}
                    onRemoveFilter={(filterId, value) => apply(withoutFilterValue(applied, filterId, value))}
                    onOpenFilters={() => setPanel("filters")}
                  />
                </div>
              ) : null}
            </div>
            {applied ? (
              <div className="w-full min-w-0 sm:w-auto sm:shrink-0">
                <ReportActions
                  activeFilters={activeCount}
                  onOpenFilters={() => setPanel((current) => togglePanel(current, "filters"))}
                  onOpenParams={() => setPanel((current) => togglePanel(current, "params"))}
                  alwaysVisible={1}
                  actions={[
                    {
                      id: "pdf",
                      label: t.reportActions.pdf,
                      icon: FileDown,
                      onClick: () => void handlePdf(),
                      show: report.pdf && query !== null,
                      loading: pdfBusy,
                    },
                  ]}
                />
              </div>
            ) : null}
          </div>

          {pdfError && <Alert tone="error">{pdfError}</Alert>}
          {dataError && <Alert tone="error">{dataError}</Alert>}
          {fresh && data && isStale(data) && <Alert tone="warning">{staleText(data)}</Alert>}

          <ReportArea
            theme={tokens}
            mode={areaMode}
            className={`space-y-5 transition-opacity motion-reduce:transition-none ${
              dataLoading || !fresh ? "opacity-60" : ""
            }`}
            aria-busy={dataLoading || undefined}
            inert={!fresh || dataLoading ? true : undefined}
          >
            {dataLoading && !data && (
              <div role="status" className="flex justify-center py-8 text-accent">
                <Spinner className="h-8 w-8" />
                <span className="sr-only">{t.common.loading}</span>
              </div>
            )}
            {data && <ReportViews data={data} def={report} onViewAsTable={openTable} />}
          </ReportArea>
        </div>
      </PageContainer>

      {tableCard && data && report ? (
        <CardDialog
          open
          title={t.reportParams.dataTable.title(tableCard.title)}
          onClose={closeTable}
          period={t.reportParams.periodLabels[data.selection.period] ?? data.selection.period}
          comparison={data.selection.previous && data.selection.compare !== "none"
            ? t.reportParams.compareLabels[data.selection.compare] : undefined}
          filters={Object.entries(data.filters ?? {})
            .flatMap(([field, values]) => values.map((value) => `${field}: ${value}`))}
        >
          <CardDataTable
            view={tableCard.view}
            options={{
              component: tableCard.component,
              def: report,
              filters: data.filters,
              trend: (metric) => data.views.find(
                (view): view is Extract<ReportData["views"][number], { type: "trend" }> =>
                  view.type === "trend" && view.metric === metric),
            }}
            currency={report.currency}
            hideExport={!report.pdf}
          />
        </CardDialog>
      ) : null}

      <ReportSheet
        open={panel !== null}
        title={t.reportActions.filters(activeCount)}
        onClose={() => setPanel(null)}
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
            <Button variant="primary" block onClick={() => setPanel(null)}>
              {t.reportSheet.done}
            </Button>
          </div>
        }
      >
        {applied && panel === "filters" ? (
          <ParamsForm
            def={report}
            applied={applied}
            onApply={apply}
            loadOptions={loadOptions}
            live
            section="filters"
            className="space-y-5"
          />
        ) : null}
        {applied && panel === "params" ? (
          <ReportParamsPanel
            def={report}
            applied={applied}
            onApply={apply}
            loadOptions={loadOptions}
          />
        ) : null}
      </ReportSheet>

      {branding.legal_privacy_url || branding.legal_terms_url ? (
        <footer className="border-t border-line bg-surface">
          <PageContainer className="py-4 text-center text-xs text-ink-soft">
            <LegalLinks
              privacyUrl={branding.legal_privacy_url}
              termsUrl={branding.legal_terms_url}
            />
          </PageContainer>
        </footer>
      ) : null}
    </div>
  );
}
