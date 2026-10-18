import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { FileDown, Link2Off, RefreshCw, SlidersHorizontal } from "lucide-react";
import { api, ApiError } from "../api/client";
import type {
  ReportData,
  ReportDefinition,
  SharedDashboard as SharedDashboardData,
} from "../api/types";
import { ParamsForm } from "../components/report/ParamsForm";
import { ContextBlock } from "../components/report/ContextBlock";
import { ReportViews } from "../components/report/ReportViews";
import type { MultiSelectOptions } from "../components/MultiSelect";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { Logo } from "../components/Logo";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";
import { localized } from "../lib/labels";
import { downloadPdf } from "../lib/download";
import { formatDate } from "../lib/format";
import { isStale, staleText } from "../lib/freshness";
import {
  filterOptionsQuery,
  isIncompleteCustom,
  parseSelection,
  sameSelection,
  selectionQuery,
  serializeSelection,
  withoutFilterValue,
} from "../lib/reportQuery";
import type { ReportSelection } from "../lib/reportQuery";
import { errorText } from "../lib/sharing";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Spinner } from "../components/Spinner";

type LoadState =
  | { status: "loading" }
  | { status: "expired" }
  | { status: "throttled" }
  | { status: "error"; message: string }
  | { status: "ok"; shared: SharedDashboardData };

/** Public, read-only view of one dashboard through an expiring share link (feature 018). */
export function SharedDashboard() {
  const t = useT();
  const { token = "" } = useParams();
  const base = `/api/shared/${encodeURIComponent(token)}`;
  const [params, setParams] = useSearchParams();
  const branding = useBranding();

  const [sharedState, setSharedState] = useState<LoadState>({
    status: "loading",
  });
  const [data, setData] = useState<ReportData | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataQuery, setDataQuery] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const previousTitleRef = useRef<string>(document.title);

  const report = useMemo<ReportDefinition | null>(
    () =>
      sharedState.status === "ok"
        ? { ...sharedState.shared.report, ai_narrative: false }
        : null,
    [sharedState],
  );

  const applied = useMemo(
    () => (report ? parseSelection(params, report) : null),
    [params, report],
  );

  const apply = useCallback(
    (s: ReportSelection) => {
      if (!report || !applied || sameSelection(s, applied)) {
        return;
      }
      setParams(serializeSelection(s, report), { replace: true });
    },
    [report, applied, setParams],
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
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
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
      </main>
    );
  }

  const sharedData = sharedState.shared;
  const orgName =
    branding.organization_name || branding.product_name;

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
          <Logo className="h-8 w-8" />
          <span className="min-w-0 truncate font-semibold text-ink">{orgName}</span>
          <div className="ml-auto shrink-0">
            <LanguageSwitcher compact />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <div className="space-y-5">
          <Alert tone="info">
            {t.sharing.shared.banner(formatDate(sharedData.expires_at))}
          </Alert>

          <div>
            <h1 className="text-2xl font-bold text-ink sm:text-3xl">
              {localized(sharedData.dashboard, "name")}
            </h1>
            {localized(report, "description") && (
              <p className="mt-1 text-sm text-ink-2">
                {localized(report, "description")}
              </p>
            )}
          </div>

          <div className="space-y-5">
            {applied && (
              <ContextBlock
                def={report}
                applied={applied}
                data={fresh ? data : null}
                incompleteCustom={incompleteCustom}
                onRemoveFilter={(filterId, value) =>
                  apply(withoutFilterValue(applied, filterId, value))
                }
                viewer={null}
                actions={
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="secondary"
                      icon={
                        <SlidersHorizontal
                          className="h-5 w-5"
                          aria-hidden
                        />
                      }
                      className="lg:hidden"
                      aria-expanded={showFilters}
                      onClick={() => setShowFilters((v) => !v)}
                    >
                      {showFilters
                        ? t.sharing.shared.hideFilters
                        : t.sharing.shared.filters}
                    </Button>
                    {report.pdf && query !== null && (
                      <Button
                        variant="secondary"
                        icon={<FileDown className="h-5 w-5" aria-hidden />}
                        loading={pdfBusy}
                        onClick={() => void handlePdf()}
                      >
                        {t.reportParams.downloadPdf}
                      </Button>
                    )}
                  </div>
                }
              />
            )}

            {pdfError && <Alert tone="error">{pdfError}</Alert>}
            {dataError && <Alert tone="error">{dataError}</Alert>}
            {fresh && data && isStale(data) && (
              <Alert tone="warning">{staleText(data)}</Alert>
            )}
          </div>

          <div className="lg:grid lg:grid-cols-[20rem_minmax(0,1fr)] lg:items-start lg:gap-6">
            <Card
              className={`${showFilters ? "block" : "hidden"} mb-5 p-5 lg:mb-0 lg:block`}
            >
              {applied && (
                <ParamsForm
                  def={report}
                  applied={applied}
                  onApply={apply}
                  loadOptions={loadOptions}
                  className="space-y-5"
                >
                  <Button
                    variant="ghost"
                    className="mt-2 lg:hidden"
                    icon={
                      <SlidersHorizontal className="h-5 w-5" aria-hidden />
                    }
                    onClick={() => setShowFilters(false)}
                  >
                    {t.sharing.shared.hideFilters}
                  </Button>
                </ParamsForm>
              )}
            </Card>

            <div
              className={`space-y-5 transition-opacity motion-reduce:transition-none ${
                dataLoading || !fresh ? "opacity-60" : ""
              }`}
              aria-busy={dataLoading || undefined}
              inert={!fresh || dataLoading ? true : undefined}
            >
              {dataLoading && !data && (
                <div
                  role="status"
                  className="flex justify-center py-8 text-accent"
                >
                  <Spinner className="h-8 w-8" />
                  <span className="sr-only">{t.common.loading}</span>
                </div>
              )}
              {data && <ReportViews data={data} def={report} />}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
