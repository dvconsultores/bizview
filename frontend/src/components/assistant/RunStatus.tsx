import { useEffect, useRef, useState } from "react";
import { Loader2, Square } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type { AssistantSession } from "../../api/types";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { Button } from "../Button";

export function RunStatus({
  session,
  busy,
  onSession,
  release,
}: {
  session: AssistantSession;
  busy: boolean;
  onSession: (s: AssistantSession) => void;
  release: () => void;
}) {
  const t = useT();
  const [stopping, setStopping] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    setStopped(false);
    setError(null);
  }, [session.id]);

  useEffect(() => {
    if (busy) setStopped(false);
  }, [busy]);

  const stop = async () => {
    setStopping(true);
    setError(null);
    try {
      const s = await api.post<AssistantSession>(`/api/assistant/sessions/${session.id}/stop`);
      if (!mountedRef.current) return;
      release();
      onSession(s);
      setStopped(true);
    } catch (e) {
      if (!mountedRef.current) return;
      if (e instanceof ApiError && e.status === 409 && e.code === "not_running") {
        release();
        try {
          const refreshed = await api.get<AssistantSession>(`/api/assistant/sessions/${session.id}`);
          if (mountedRef.current) onSession(refreshed);
        } catch {
          // ignore refresh errors after not_running
        }
      } else {
        setError(e instanceof ApiError ? e.message : t.assistant.failedToStop);
      }
    } finally {
      if (mountedRef.current) setStopping(false);
    }
  };

  // Feature 028 (FR-006): the contract's stage, spend and elapsed time, live while the run lasts.
  const contract = session.contract;
  // Feature 039: the eight-stage plan, when one is running.
  const pipeline = session.command_runs?.find((run) => run.pipeline)?.pipeline ?? null;
  const liveContract =
    session.mode === "auto" && contract && (contract.status === "running" ||
      contract.status === "confirmed");

  if (busy) {
    return (
      <div className="flex flex-col gap-2">
        {liveContract ? (
          <dl
            data-run-status=""
            className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted"
          >
            {contract.stage || pipeline ? (
              <div className="flex items-center gap-1">
                <dt className="sr-only">{t.assistant.runStatus.stage}</dt>
                <dd className="inline-flex items-center rounded-full border border-line bg-surface px-2 py-0.5 font-medium text-ink-2">
                  {pipeline
                    ? `${t.assistant.runReport.stagePosition
                        .replace("{step}", String(Math.min(pipeline.cursor + 1, pipeline.total)))
                        .replace("{total}", String(pipeline.total))}${
                        pipeline.stage ? ` · ${pipeline.stage}` : ""}`
                    : contract?.stage}
                </dd>
              </div>
            ) : null}
            <div className="flex items-center gap-1">
              <dt>{t.assistant.runStatus.tokens}</dt>
              <dd>
                {contract.used.tokens} / {contract.limits.tokens}
              </dd>
            </div>
            <div className="flex items-center gap-1">
              <dt>{t.assistant.runStatus.previews}</dt>
              <dd>
                {contract.used.previews} / {contract.limits.previews}
              </dd>
            </div>
            <div className="flex items-center gap-1">
              <dt>{t.assistant.runStatus.applies}</dt>
              <dd>
                {contract.used.applies} / {contract.limits.applies}
              </dd>
            </div>
            <div className="flex items-center gap-1">
              <dt>{t.assistant.runStatus.elapsed}</dt>
              <dd>
                {t.assistant.runStatus.elapsedValue
                  .replace("{used}", String(Math.floor(contract.used.elapsed_seconds / 60)))
                  .replace(
                    "{total}",
                    String(Math.round(contract.limits.wall_clock_seconds / 60)),
                  )}
              </dd>
            </div>
          </dl>
        ) : null}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <div role="status" className="flex items-center gap-2 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            {t.assistant.busyStatus}
          </div>
          <Button variant="secondary" icon={<Square className="h-4 w-4" aria-hidden />} loading={stopping} onClick={stop}>
            {t.assistant.stop}
          </Button>
        </div>
        {error ? <Alert tone="error">{error}</Alert> : null}
      </div>
    );
  }

  if (stopped) {
    return (
      <div className="flex flex-col gap-2">
        <p role="status" className="text-sm text-ink-muted">
          {t.assistant.stopped}
        </p>
        {error ? <Alert tone="error">{error}</Alert> : null}
      </div>
    );
  }

  // A contract that ended by itself says why (limit, blocked stage, revoked role).
  const stopReason = session.contract?.stop_reason;
  if (session.mode === "auto" && stopReason) {
    const name = stopReason.startsWith("limit:") ? stopReason.slice(6) : null;
    const names = t.assistant.runStatus.limitNames as Record<string, string>;
    const limit = name ? (names[name] ?? name) : null;
    return (
      <p role="status" data-contract-stop="" className="text-sm text-ink-muted">
        {limit
          ? t.assistant.runStatus.stoppedByLimit.replace("{limit}", limit)
          : t.assistant.pill.stopped}
      </p>
    );
  }

  if (error) {
    return <Alert tone="error">{error}</Alert>;
  }

  return null;
}
