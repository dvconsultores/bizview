import { useEffect, useRef, useState } from "react";
import { projectsApi } from "../../api/projects";

const BUSY_MS = 2000;
const IDLE_MS = 15000;

/** Research R12: poll the project's revisions — every 2 s while a conversation is working on
 * it, every 15 s otherwise and when the window regains focus — and report the changed paths. */
export function useProjectChanges(
  slug: string,
  opts: { onChanges: (paths: string[], busy: boolean) => void; enabled?: boolean },
): { busy: boolean } {
  const enabled = opts.enabled ?? true;
  const [busy, setBusy] = useState(false);
  const onChanges = useRef(opts.onChanges);
  onChanges.current = opts.onChanges;

  useEffect(() => {
    if (!enabled || !slug) return;
    let stopped = false;
    let after: number | null = null;
    let lastBusy = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let inFlight = false;

    const schedule = () => {
      clearTimeout(timer);
      if (!stopped) timer = setTimeout(poll, lastBusy ? BUSY_MS : IDLE_MS);
    };
    const poll = async () => {
      if (stopped || inFlight) return;
      inFlight = true;
      try {
        const res = await projectsApi.changes(slug, after ?? 0);
        if (stopped) return;
        const first = after === null;
        after = res.latest;
        const busyChanged = res.busy !== lastBusy;
        lastBusy = res.busy;
        setBusy(res.busy);
        const paths = first ? [] : [...new Set(res.items.map((i) => i.path))];
        if (paths.length || busyChanged) onChanges.current(paths, res.busy);
      } catch {
        /* offline or server busy: try again later */
      } finally {
        inFlight = false;
        schedule();
      }
    };
    const now = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        void poll();
      }
    };
    void poll();
    window.addEventListener("focus", now);
    document.addEventListener("visibilitychange", now);
    return () => {
      stopped = true;
      clearTimeout(timer);
      window.removeEventListener("focus", now);
      document.removeEventListener("visibilitychange", now);
    };
  }, [slug, enabled]);

  return { busy };
}
