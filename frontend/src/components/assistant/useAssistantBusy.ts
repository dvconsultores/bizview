import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { AssistantSession } from "../../api/types";

export const BUSY_POLL_MS = 3000;

export function isAssistantBusy(e: unknown): boolean {
  return e instanceof ApiError && e.status === 409 && e.code === "assistant_busy";
}

export function isAssistantCapacity(e: unknown): boolean {
  return e instanceof ApiError && e.status === 409 && e.code === "assistant_capacity";
}

/**
 * Tracks server-side "busy" state for an assistant session and polls the
 * session endpoint until the server finishes the current agent turn.
 */
export function useAssistantBusy(
  session: AssistantSession | null,
  onSession: (s: AssistantSession) => void,
): { busy: boolean; markBusy: () => void; release: () => void } {
  const [forced, setForced] = useState(false);
  const onSessionRef = useRef(onSession);
  onSessionRef.current = onSession;

  const id = session?.id ?? null;
  const busy = forced || !!session?.busy;

  // Reset forced when switching to a different session.
  useEffect(() => {
    setForced(false);
  }, [id]);

  useEffect(() => {
    if (!busy || !id) return;

    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        const s = await api.get<AssistantSession>(`/api/assistant/sessions/${id}`);
        if (cancelled) return;
        onSessionRef.current(s);
        if (!s.busy) {
          setForced(false);
          return;
        }
      } catch {
        // keep polling on transient errors
      }
      if (!cancelled) {
        timer = window.setTimeout(poll, BUSY_POLL_MS);
      }
    };

    timer = window.setTimeout(poll, BUSY_POLL_MS);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [busy, id]);

  const markBusy = useCallback(() => setForced(true), []);
  const release = useCallback(() => setForced(false), []);

  return { busy, markBusy, release };
}
