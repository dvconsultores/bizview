import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { formatDateTime } from "../../lib/format";
import { Button } from "../Button";
import { Card } from "../Card";
import { useT } from "../../i18n";

/** AI summary on demand: only the aggregates the report spec lists are sent (backend). */
export function Narrative({ reportId, query }: { reportId: string; query: string }) {
  const t = useT();
  const [state, setState] = useState<{ text: string; at: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setState(null);
    setError(null);
  }, [query]);

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .get<{ text: string; generated_at: string }>(`/api/reports/${encodeURIComponent(reportId)}/narrative${query}`)
      .then((r) => setState({ text: r.text, at: r.generated_at }))
      .catch((e) => setError(e instanceof ApiError ? e.message : t.reportParams.display.narrativeFailed))
      .finally(() => setLoading(false));
  };

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between">
        <h2 className="mr-3 flex items-center text-lg font-semibold text-ink">
          <span className="mr-3 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <Sparkles className="h-5 w-5" aria-hidden />
          </span>
          {t.reportParams.display.aiSummary}
        </h2>
        {!state ? (
          <Button variant="secondary" loading={loading} onClick={load} className="mt-2 sm:mt-0">
            {t.reportParams.display.generateSummary}
          </Button>
        ) : null}
      </div>
      <div aria-live="polite">
        {state ? (
          <>
            <p className="mt-3 whitespace-pre-line text-ink-2">{state.text}</p>
            <p className="mt-2 text-xs text-ink-soft">{t.reportParams.display.generatedAt(formatDateTime(state.at))}</p>
          </>
        ) : error ? (
          <p role="alert" className="mt-3 text-sm text-danger-strong">{error}</p>
        ) : (
          <p className="mt-2 text-sm text-ink-muted">{t.reportParams.display.aiPrivacyNote}</p>
        )}
      </div>
    </Card>
  );
}
