import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { FileDown, Link2Off, RefreshCw } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { MultiSelectOptions } from "../components/MultiSelect";
import type { ReportData, WidgetDefinition } from "../api/types";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { CardDataTable } from "../components/report/CardDataTable";
import { CardDialog } from "../components/report/CardDialog";
import { ParamsForm } from "../components/report/ParamsForm";
import { ReportActions } from "../components/report/ReportActions";
import { ReportArea } from "../components/report/ReportArea";
import { ReportMetaLine } from "../components/report/ReportMetaLine";
import { ReportParamsPanel } from "../components/report/ReportParamsPanel";
import { ReportSheet } from "../components/report/ReportSheet";
import { ReportViews } from "../components/report/ReportViews";
import { LegalLinks } from "../components/LegalLinks";
import { Spinner } from "../components/Spinner";
import { useBranding } from "../config/BrandingContext";
import { LocaleProvider, useT } from "../i18n";
import { downloadPdf } from "../lib/download";
import { isStale, staleText } from "../lib/freshness";
import { localized } from "../lib/labels";
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
import { tableEntry } from "../lib/reportTable";
import { parseViewState, togglePanel } from "../lib/reportView";
import { errorText } from "../lib/sharing";
import { reportMode } from "../theme/library";
import type { ThemeMode } from "../theme/themes";
import { ThemeProvider, useTheme } from "../theme/ThemeContext";

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "throttled" }
  | { status: "error"; message: string }
  | { status: "ok"; definition: WidgetDefinition };

/**
 * Feature 065: the framed document of a widget (`/w/<token>`).
 *
 * It is deliberately not the report page and not the share-link page: no navigation, no account
 * controls, no language or theme switchers (the widget decides those), nothing that leads back into
 * the product. The only way out is the installation's legal pages (FR-023).
 *
 * Sizing travels to the host page as `{type, widget, height}` and carries no data; the parent script
 * in the snippet checks this document's origin, and this page only answers a parent whose origin is
 * on the widget's own list (FR-017).
 */
export function WidgetView() {
  const { token = "" } = useParams();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const definition = state.status === "ok" ? state.definition : null;
  const options = definition?.widget ?? null;

  // The widget pins the theme and the language when the admin chose them; otherwise the visitor's
  // device decides, exactly as everywhere else (FR-024).
  return (
    <ThemeProvider force={options?.theme ?? null}>
      <LocaleProvider force={options?.language ?? null}>
        <WidgetDocument token={token} state={state} setState={setState} />
      </LocaleProvider>
    </ThemeProvider>
  );
}

function WidgetDocument({
  token,
  state,
  setState,
}: {
  token: string;
  state: LoadState;
  setState: (state: LoadState) => void;
}) {
  const t = useT();
  const base = `/api/widgets/${encodeURIComponent(token)}`;
  const [params, setParams] = useSearchParams();
  const tableId = params.get("tabla");
  const definition = state.status === "ok" ? state.definition : null;
  const report = definition?.report ?? null;
  const options = definition?.widget ?? null;
  const branding = useBranding();
  const { resolved, tokens } = useTheme();

  const [data, setData] = useState<ReportData | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataQuery, setDataQuery] = useState<string | null>(null);
  const [panel, setPanel] = useState<"filters" | "params" | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const openTable = (id: string) => {
    const next = new URLSearchParams(params);
    next.set("tabla", id);
    setParams(next);
  };
  const closeTable = () => {
    const next = new URLSearchParams(params);
    next.delete("tabla");
    setParams(next, { replace: true });
  };

  // FR-024: with the controls switched off the widget shows the report's defaults — the address
  // cannot change what is served (the API ignores period/compare/filters too) and the chips lie.
  const filtersOn = options?.show_filters ?? true;
  const applied = useMemo(
    () => (report ? (filtersOn ? parseSelection(params, report) : defaultSelection(report)) : null),
    [params, report, filtersOn],
  );

  const activeCount = useMemo(() => {
    if (!applied || !report) return 0;
    return report.filters.reduce((sum, id) => sum + (applied.filters[id]?.length ?? 0), 0);
  }, [applied, report]);

  const apply = useCallback(
    (selection: ReportSelection) => {
      if (!report || !applied || sameSelection(selection, applied)) return;
      const next = serializeSelection(selection, report);
      for (const [key, value] of Object.entries(parseViewState(params))) {
        if (value !== null) next.set(key, value);
      }
      setParams(next, { replace: true });
    },
    [report, applied, params, setParams],
  );

  const loadOptions = useCallback(
    (filterId: string, selection: ReportSelection, q: string) =>
      api.get<MultiSelectOptions>(
        `${base}/filters/${encodeURIComponent(filterId)}${filterOptionsQuery(selection, q)}`,
      ),
    [base],
  );

  // The origin that framed this document, from the browser (not from the page's own URL): the
  // backend answers whether that single origin is allowed, and never lists the widget's sites
  // (FR-008). The snippet's iframe asks for at least the origin, so a host page's referrer policy
  // cannot hide it.
  const framedBy = useMemo(() => {
    const referrer = document.referrer;
    if (!referrer) return null;
    try {
      return new URL(referrer).origin;
    } catch {
      return null;
    }
  }, []);

  const load = useCallback(async () => {
    setState({ status: "loading" });
    setDataError(null);
    try {
      const query = framedBy ? `?parent=${encodeURIComponent(framedBy)}` : "";
      const loaded = await api.get<WidgetDefinition>(base + query);
      setState({ status: "ok", definition: loaded });
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 429) {
          setState({ status: "throttled" });
          return;
        }
        if (e.status >= 400 && e.status < 500) {
          // Revoked, expired, replaced, withdrawn, off: one neutral message (FR-013).
          setState({ status: "unavailable" });
          return;
        }
      }
      setState({ status: "error", message: errorText(e) });
    }
  }, [base, framedBy, setState]);

  useEffect(() => {
    void load();
  }, [load]);

  // FR-014: no search engine indexes it and nothing keeps it after the visit.
  useEffect(() => {
    const made: HTMLMetaElement[] = [];
    for (const [name, content] of [
      ["robots", "noindex, nofollow"],
      ["referrer", "no-referrer"],
    ] as const) {
      const meta = document.createElement("meta");
      meta.name = name;
      meta.content = content;
      made.push(meta);
      document.head.appendChild(meta);
    }
    return () => made.forEach((meta) => document.head.removeChild(meta));
  }, []);

  const incompleteCustom = applied ? isIncompleteCustom(applied) : false;
  const query =
    applied && report && !incompleteCustom ? selectionQuery(applied, report) : null;

  useEffect(() => {
    if (!report || query === null) return;
    let cancelled = false;
    setDataLoading(true);
    setDataError(null);
    setPdfError(null);
    api
      .get<ReportData>(`${base}/data${query}`)
      .then((payload) => {
        if (cancelled) return;
        setData(payload);
        setDataQuery(query);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setState({ status: "unavailable" });
        } else if (e instanceof ApiError && e.status === 429) {
          setState({ status: "throttled" });
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
  }, [base, report, query, setState]);

  useWidgetHeight(
    options?.id ?? null,
    options?.parent_origin ?? null,
    state.status === "ok",
  );

  const fresh = data !== null && dataQuery === query;
  const tableCard = tableId && data && report ? tableEntry(tableId, data, report) : null;

  const handlePdf = async () => {
    if (!report || !query) return;
    setPdfBusy(true);
    setPdfError(null);
    try {
      await downloadPdf(`${base}/pdf${query}`, `${report.id}.pdf`, t.reportParams.pdfError);
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : t.reportParams.pdfError);
    } finally {
      setPdfBusy(false);
    }
  };

  const stateCard = (title: string, text: string, retry: boolean) => (
    <main className="flex w-full items-start justify-center px-4 py-8">
      <Card className="w-full max-w-md p-6 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-2 text-ink-muted">
          <Link2Off className="h-6 w-6" aria-hidden />
        </div>
        <h1 className="text-lg font-bold text-ink">{title}</h1>
        <p className="mt-2 text-sm text-ink-2">{text}</p>
        {retry ? (
          <div className="mt-5 flex justify-center">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-5 w-5" aria-hidden />}
              onClick={() => void load()}
            >
              {t.common.retry}
            </Button>
          </div>
        ) : null}
      </Card>
    </main>
  );

  if (state.status === "loading") {
    return (
      <div className="flex w-full items-center justify-center py-10">
        <div role="status" className="flex justify-center py-6 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      </div>
    );
  }
  if (state.status === "unavailable") {
    return stateCard(t.widgets.widgetUnavailableTitle, t.widgets.widgetUnavailableText, false);
  }
  if (state.status === "throttled") {
    return stateCard(t.widgets.widgetBusyTitle, t.widgets.widgetBusyText, true);
  }
  if (state.status === "error" || !definition || !report || !options) {
    return stateCard(
      t.sharing.shared.expiredTitle,
      state.status === "error" ? state.message : t.common.unexpected,
      true,
    );
  }

  const declared = reportMode(report.layout?.theme);
  const areaMode: ThemeMode = options.theme ?? (declared === "auto" ? resolved : declared);
  const title = localized(definition.dashboard, "name");
  const showTitle = options.show_title && !!title;
  const showFilters = options.show_filters && !!applied;
  const orgName = branding.organization_name || branding.product_name;

  return (
    <div className="w-full bg-canvas">
      <main className="w-full space-y-4 px-3 py-3 sm:px-4">
        {(showTitle || applied || options.pdf) && (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              {showTitle ? <h1 className="text-xl font-bold text-ink sm:text-2xl">{title}</h1> : null}
              {applied ? (
                <div className={showTitle ? "mt-2" : ""}>
                  <ReportMetaLine
                    def={report}
                    applied={applied}
                    data={fresh ? data : null}
                    // With the controls switched off there are no applied filters to remove, so
                    // these callbacks never render a control (FR-024).
                    onRemoveFilter={(filterId, value) =>
                      showFilters ? apply(withoutFilterValue(applied, filterId, value)) : undefined}
                    onOpenFilters={() => showFilters && setPanel("filters")}
                  />
                </div>
              ) : null}
            </div>
            {showFilters ? (
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
                      show: options.pdf && query !== null,
                      loading: pdfBusy,
                    },
                  ]}
                />
              </div>
            ) : options.pdf ? (
              // No filter controls, but the PDF the admin allowed is still one plain button.
              <div className="shrink-0">
                <Button
                  variant="secondary"
                  icon={<FileDown className="h-5 w-5" aria-hidden />}
                  onClick={() => void handlePdf()}
                  loading={pdfBusy}
                  disabled={query === null}
                >
                  {t.reportActions.pdf}
                </Button>
              </div>
            ) : null}
          </div>
        )}

        {pdfError && <Alert tone="error">{pdfError}</Alert>}
        {dataError && <Alert tone="error">{dataError}</Alert>}
        {fresh && data && isStale(data) && <Alert tone="warning">{staleText(data)}</Alert>}

        <ReportArea
          theme={tokens}
          mode={areaMode}
          className={`space-y-4 transition-opacity motion-reduce:transition-none ${
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

        {/* FR-023: the installation's legal pages stay reachable; nothing else leads into the product. */}
        {branding.legal_privacy_url || branding.legal_terms_url || orgName ? (
          <footer className="border-t border-line pt-2 text-center text-xs text-ink-soft">
            <LegalLinks
              privacyUrl={branding.legal_privacy_url}
              termsUrl={branding.legal_terms_url}
            />
          </footer>
        ) : null}
      </main>

      {tableCard && data && report ? (
        <CardDialog
          open
          title={t.reportParams.dataTable.title(tableCard.title)}
          onClose={closeTable}
          period={t.reportParams.periodLabels[data.selection.period] ?? data.selection.period}
          comparison={
            data.selection.previous && data.selection.compare !== "none"
              ? t.reportParams.compareLabels[data.selection.compare]
              : undefined
          }
          filters={Object.entries(data.filters ?? {}).flatMap(([field, values]) =>
            values.map((value) => `${field}: ${value}`),
          )}
        >
          <CardDataTable
            view={tableCard.view}
            options={{
              component: tableCard.component,
              def: report,
              filters: data.filters,
              trend: (metric) =>
                data.views.find(
                  (view): view is Extract<ReportData["views"][number], { type: "trend" }> =>
                    view.type === "trend" && view.metric === metric,
                ),
            }}
            currency={report.currency}
            hideExport={!options.pdf}
          />
        </CardDialog>
      ) : null}

      {showFilters ? (
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
              <Button
                variant="ghost"
                block
                onClick={() => {
                  if (applied && report) {
                    setParams(serializeSelection(defaultSelection(report), report), {
                      replace: true,
                    });
                  }
                }}
              >
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
      ) : null}
    </div>
  );
}

/**
 * Tell the host page how tall the content is (FR-025), and answer its pings.
 *
 * The message is `{type, widget, height}`: no dashboard data, no key. `parentOrigin` is the one
 * origin the backend confirmed for this document (FR-017); without one the page posts nothing, so a
 * document framed by an unlisted site cannot even leak its height. The snippet only listens to
 * messages from this installation's origin.
 */
function useWidgetHeight(widgetId: number | null, parentOrigin: string | null, ready: boolean) {
  const marker = widgetId ? `bizview-widget-${widgetId}` : null;

  useEffect(() => {
    if (!ready || !marker || !parentOrigin) return;
    const target = parentOrigin;

    const send = () => {
      if (window.parent === window) return;
      const height = Math.max(
        160,
        Math.ceil(document.documentElement.scrollHeight),
        Math.ceil(document.body.getBoundingClientRect().height),
      );
      window.parent.postMessage({ type: "bizview:height", widget: marker, height }, target);
    };

    const onMessage = (event: MessageEvent) => {
      if (event.origin !== target) return;   // FR-017: anywhere else is ignored
      const message = event.data as { type?: unknown } | null;
      if (!message || message.type !== "bizview:ping") return;
      send();
    };
    window.addEventListener("message", onMessage);

    let last = 0;
    const notify = () => {
      const height = Math.max(
        160,
        Math.ceil(document.documentElement.scrollHeight),
        Math.ceil(document.body.getBoundingClientRect().height),
      );
      if (Math.abs(height - last) < 2) return;
      last = height;
      send();
    };
    notify();
    const observer = new ResizeObserver(notify);
    observer.observe(document.body);
    const timer = window.setTimeout(notify, 600);   // fonts and first images settle late
    return () => {
      window.removeEventListener("message", onMessage);
      observer.disconnect();
      window.clearTimeout(timer);
    };
  }, [parentOrigin, marker, ready]);
}
