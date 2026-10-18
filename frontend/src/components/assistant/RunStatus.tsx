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

  if (busy) {
    return (
      <div className="flex flex-col gap-2">
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

  if (error) {
    return <Alert tone="error">{error}</Alert>;
  }

  return null;
}
