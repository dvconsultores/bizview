import { AlertTriangle, ArrowRight, RefreshCw, Terminal, Wrench } from "lucide-react";
import { Link } from "react-router";
import type { ProviderErrorPayload } from "../../api/types";
import { useT } from "../../i18n";

/**
 * Why a turn failed, in full (feature 035): the code, the provider's own words, the model, one
 * action, and — collapsed — the timestamp, the request id and the command that reads the log.
 *
 * The reader used to see «El proveedor de IA devolvió un error» and had to guess which container
 * held the reason.
 */
export function ProviderError({ error, onRetry, onRepair, repairing = false }: {
  error: ProviderErrorPayload;
  onRetry?: () => void;
  /** 036: the stored conversation cannot be replayed; repairing it is the only way forward. */
  onRepair?: () => void;
  repairing?: boolean;
}) {
  const t = useT();
  const reason = t.ai.errorCodes[error.code] ?? t.ai.errorCodes.provider_error;
  const unrepairable = error.code === "history_invalid";
  return (
    <div role="alert"
         className="w-full rounded-card border border-danger-soft bg-danger-soft/40 px-3.5 py-3 text-sm text-ink">
      <p className="flex items-start gap-2 font-semibold">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
        <span className="min-w-0 break-words">{reason}</span>
      </p>
      <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-ink-muted">
        <span className="font-mono">{error.code}</span>
        {error.model ? <span>{t.ai.details.model}: <span className="font-mono">{error.model}</span></span> : null}
        {error.provider ? <span>({error.provider})</span> : null}
        {error.blocked ? <span className="text-danger">{t.ai.blockedTag}</span> : null}
      </p>
      {unrepairable ? (
        <p className="mt-2 text-xs text-ink-2">{t.ai.historyInvalidHint}</p>
      ) : null}
      {error.detail ? (
        <p className="mt-2 max-h-32 overflow-auto break-words rounded-lg bg-surface/70 p-2 font-mono text-xs text-ink-2">
          {error.detail}
        </p>
      ) : null}
      {error.retry_after ? (
        <p className="mt-1 text-xs text-ink-muted">
          {t.ai.retryAfter(Math.round(error.retry_after))}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {error.action === "admin_ai" ? (
          <Link to="/admin/ia"
                className="inline-flex min-h-tap items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-on-accent hover:bg-accent-deep focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
            {t.ai.action.admin_ai}
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        ) : null}
        {unrepairable && onRepair ? (
          <button type="button" onClick={onRepair} disabled={repairing}
                  className="inline-flex min-h-tap items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-on-accent hover:bg-accent-deep disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
            <Wrench className="h-4 w-4" aria-hidden />
            {repairing ? t.ai.repairing : t.ai.repair}
          </button>
        ) : null}
        {error.action === "retry" && onRetry ? (
          <button type="button" onClick={onRetry}
                  className="inline-flex min-h-tap items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-semibold text-ink-2 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
            <RefreshCw className="h-4 w-4" aria-hidden />
            {t.ai.action.retry}
          </button>
        ) : null}
      </div>
      <details className="mt-2 text-xs text-ink-muted">
        <summary className="inline-flex cursor-pointer items-center gap-1">
          <Terminal className="h-3.5 w-3.5" aria-hidden />
          {t.ai.details.title}
        </summary>
        <dl className="mt-1 space-y-1">
          <div className="flex flex-wrap gap-1">
            <dt className="font-semibold">{t.ai.details.at}:</dt>
            <dd>{new Date(error.at).toLocaleString()}</dd>
          </div>
          <div className="flex flex-wrap gap-1">
            <dt className="font-semibold">{t.ai.details.request}:</dt>
            <dd className="font-mono">{error.request_id}</dd>
          </div>
          <div>
            <dt className="font-semibold">{t.ai.details.log}</dt>
            <dd className="mt-1 overflow-x-auto rounded bg-surface/70 p-2 font-mono text-[11px]">
              {t.ai.details.cmd}
            </dd>
          </div>
        </dl>
      </details>
    </div>
  );
}
