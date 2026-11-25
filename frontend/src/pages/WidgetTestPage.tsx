import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import type { DashboardWidget, WidgetPreview, WidgetsState } from "../api/types";
import { Alert } from "../components/Alert";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { CopyButton } from "../components/CopyButton";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { Spinner } from "../components/Spinner";
import { heldSnippet } from "../lib/widgetSnippet";
import { useT } from "../i18n";
import { errorText } from "../lib/sharing";

type Width = "phone" | "tablet" | "desktop";
const WIDTHS: Record<Width, string> = { phone: "375px", tablet: "768px", desktop: "100%" };

/**
 * Feature 065 (FR-018/019): the widget framed exactly as a foreign page holds it, at the three
 * widths an admin cares about, next to its snippet and its allowed sites.
 *
 * It goes through the widget's own sessionless door with a short-lived ticket (`/w/pv.…`), not the
 * widget's key, so the key stays one-way. The snippet (the only thing holding the key) is shown only
 * when this page was reached from the creation or replacement screen in the same page session: it is
 * held in memory there and is never written to browser storage (FR-002). The preview never counts as
 * a visit.
 */
export function WidgetTestPage() {
  const t = useT();
  const { code = "", id = "" } = useParams();
  const widgetId = Number(id);
  const [widget, setWidget] = useState<DashboardWidget | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [width, setWidth] = useState<Width>("phone");
  const [frameHeight, setFrameHeight] = useState(480);
  // Held in memory by the panel when this widget was created or replaced in this page session;
  // never in storage, so a reload loses it (FR-002).
  const [snippet] = useState<string | null>(() =>
    Number.isFinite(widgetId) ? heldSnippet(code, widgetId) : null,
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const state = await api.get<WidgetsState>(
        `/api/dashboards/${encodeURIComponent(code)}/widgets`,
      );
      const found = state.items.find((item) => item.id === widgetId) ?? null;
      setWidget(found);
      if (!found || !found.active) {
        setPreview(null);
        return;
      }
      const minted = await api.post<WidgetPreview>(
        `/api/dashboards/${encodeURIComponent(code)}/widgets/${widgetId}/frame`,
        {},
      );
      // The API answers the address a developer would paste; the test page stays on this origin.
      const path = new URL(minted.url).pathname;
      setPreview(path);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [code, widgetId]);

  useEffect(() => {
    void load();
  }, [load]);

  // The framed widget reports its content height (FR-025): the test page shows it growing, with no
  // inner scrollbar, at every width.
  useEffect(() => {
    if (!preview || !widget) return;
    const marker = `bizview-widget-${widget.id}`;
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;   // FR-017
      const data = event.data as { type?: unknown; widget?: unknown; height?: unknown } | null;
      if (!data || data.type !== "bizview:height" || data.widget !== marker) return;
      if (typeof data.height !== "number" || !Number.isFinite(data.height)) return;
      setFrameHeight(Math.max(160, Math.min(4000, Math.round(data.height))));
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [preview, widget]);

  return (
    <PageContainer className="py-6">
      <div className="mb-4">
        <Link
          to={`/d/${encodeURIComponent(code)}`}
          className="inline-flex min-h-tap items-center gap-2 text-sm font-semibold text-accent hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t.widgets.testPage.back}
        </Link>
      </div>

      {loading ? (
        <div role="status" className="flex justify-center py-10 text-accent">
          <Spinner className="h-8 w-8" />
          <span className="sr-only">{t.common.loading}</span>
        </div>
      ) : null}

      {error ? (
        <Alert
          tone="error"
          action={
            <Button variant="secondary" icon={<RefreshCw className="h-5 w-5" aria-hidden />}
                    onClick={() => void load()}>
              {t.common.retry}
            </Button>
          }
        >
          {error}
        </Alert>
      ) : null}

      {widget ? (
        <div className="space-y-5">
          <PageHeader
            title={t.widgets.testPage.title(widget.name)}
            subtitle={t.widgets.testPage.intro}
          />

          <Alert tone="warning">{t.widgets.warning}</Alert>

          <Card className="p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <SegmentedControl<Width>
                label={t.widgets.testPage.widthLabel}
                value={width}
                onChange={setWidth}
                options={[
                  { value: "phone", label: t.widgets.testPage.widths.phone },
                  { value: "tablet", label: t.widgets.testPage.widths.tablet },
                  { value: "desktop", label: t.widgets.testPage.widths.desktop },
                ]}
              />
              <Button
                variant="secondary"
                icon={<RefreshCw className="h-5 w-5" aria-hidden />}
                onClick={() => void load()}
              >
                {t.widgets.testPage.refresh}
              </Button>
            </div>

            {/* The frame is the foreign page: the widget decides its own height, the host follows. */}
            <div className="overflow-x-auto rounded-xl bg-surface-2 p-2">
              <div style={{ width: WIDTHS[width], maxWidth: "100%" }} className="mx-auto">
                {preview ? (
                  <iframe
                    src={preview}
                    title={t.widgets.testPage.title(widget.name)}
                    style={{ width: "100%", height: `${frameHeight}px`, border: 0 }}
                  />
                ) : (
                  <p className="p-6 text-center text-sm text-ink-2">
                    {widget.active
                      ? t.widgets.testPage.previewError
                      : t.sharing.statusRevoked}
                  </p>
                )}
              </div>
            </div>
          </Card>

          <section className="space-y-2">
            <h2 className="text-base font-semibold text-ink">{t.widgets.testPage.sitesTitle}</h2>
            {widget.sites.length === 0 ? (
              <p className="text-sm text-ink-2">{t.widgets.testPage.noSites}</p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                {widget.sites.map((site) => (
                  <Badge key={site.origin} tone={site.development ? "amber" : "blue"} wrap>
                    <span className="mr-1 break-all font-mono text-xs">{site.origin}</span>
                    {site.development ? (
                      <span className="text-xs font-semibold">{t.widgets.development}</span>
                    ) : null}
                  </Badge>
                ))}
              </div>
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-semibold text-ink">{t.widgets.testPage.snippetTitle}</h2>
            {snippet ? (
              <>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-subtle px-3 py-2 text-xs text-ink">
                  {snippet}
                </pre>
                <CopyButton text={snippet} />
              </>
            ) : (
              <Alert tone="info">{t.widgets.testPage.snippetMissing}</Alert>
            )}
          </section>

        </div>
      ) : null}

      {!loading && !widget && !error ? <Alert tone="error">{t.widgets.testPage.notFound}</Alert> : null}
    </PageContainer>
  );
}
