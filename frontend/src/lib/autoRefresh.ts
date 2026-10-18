import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { dateTimeFormat } from "./intl";

export type AutoRefreshMode = "off" | "data" | "1" | "5" | "15" | "60";

export const AUTO_REFRESH_MODES: AutoRefreshMode[] = ["off", "data", "1", "5", "15", "60"];

export const VERSION_CHECK_MS = 60_000;

export function autoRefreshStorageKey(reportId: string): string {
  return `bizview.autorefresh.${reportId}`;
}

export function readAutoRefreshMode(reportId: string): AutoRefreshMode {
  try {
    const raw = localStorage.getItem(autoRefreshStorageKey(reportId));
    if (raw !== null && (AUTO_REFRESH_MODES as string[]).includes(raw)) {
      return raw as AutoRefreshMode;
    }
  } catch {
    // swallow storage errors
  }
  return "off";
}

export function writeAutoRefreshMode(reportId: string, mode: AutoRefreshMode): void {
  try {
    const key = autoRefreshStorageKey(reportId);
    if (mode === "off") {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, mode);
    }
  } catch {
    // swallow storage errors
  }
}

export function useAutoRefreshMode(reportId: string): [AutoRefreshMode, (m: AutoRefreshMode) => void] {
  const [mode, setMode] = useState<AutoRefreshMode>(() => readAutoRefreshMode(reportId));

  useEffect(() => {
    setMode(readAutoRefreshMode(reportId));
  }, [reportId]);

  const setModePersisted = useCallback(
    (m: AutoRefreshMode) => {
      writeAutoRefreshMode(reportId, m);
      setMode(m);
    },
    [reportId],
  );

  return [mode, setModePersisted];
}

export function formatClock(d: Date): string {
  return dateTimeFormat({ hour: "2-digit", minute: "2-digit" }).format(d);
}

export type AutoRefreshStatus = "ok" | "offline";

export interface AutoRefreshOptions {
  mode: Exclude<AutoRefreshMode, "off">;
  fetchVersion: () => Promise<string>;
  knownVersion: () => string | null;
  onRefresh: () => Promise<boolean | void>;
  onStatus?: (s: AutoRefreshStatus) => void;
  doc?: Document;
  now?: () => number;
}

interface AutoRefreshCallbacks {
  fetchVersion: () => Promise<string>;
  knownVersion: () => string | null;
  onRefresh: () => Promise<boolean | void>;
  onStatus?: (s: AutoRefreshStatus) => void;
  doc: Document;
  now: () => number;
}

export function startAutoRefresh(options: AutoRefreshOptions): () => void {
  const o: AutoRefreshCallbacks = {
    fetchVersion: options.fetchVersion,
    knownVersion: options.knownVersion,
    onRefresh: options.onRefresh,
    onStatus: options.onStatus,
    doc: options.doc ?? document,
    now: options.now ?? Date.now,
  };

  const periodMs = options.mode === "data" ? VERSION_CHECK_MS : Number(options.mode) * 60_000;

  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let inFlight = false;
  let refreshedTo: string | null = null;
  let lastRunAt: number = o.now();
  let status: AutoRefreshStatus = "ok";
  let backoffMs = 5_000; // initial backoff: 5s

  const setStatus = (next: AutoRefreshStatus, force = false) => {
    if (stopped) return;
    if (!force && next === status) return;
    status = next;
    if (o.onStatus) o.onStatus(next);
  };

  const schedule = (delay: number) => {
    if (stopped) return;
    if (o.doc.visibilityState === "hidden") return;
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      void tick();
    }, delay);
  };

  const scheduleNormal = () => {
    if (stopped) return;
    backoffMs = 5_000;
    setStatus("ok");
    schedule(periodMs);
  };

  const handleError = (e: unknown): boolean => {
    if (stopped) return false;
    const isNetworkError =
      (e instanceof ApiError && e.status === 0) || e instanceof TypeError;
    if (isNetworkError) {
      setStatus("offline");
      schedule(backoffMs);
      backoffMs = Math.min(backoffMs * 2, periodMs);
      return true;
    }
    return false;
  };

  const tick = async () => {
    if (stopped || inFlight) return;
    if (o.doc.visibilityState === "hidden") return;

    inFlight = true;
    try {
      if (options.mode === "data") {
        const v = await o.fetchVersion();
        if (stopped) return;
        const known = o.knownVersion();
        if ((known === null || v !== known) && v !== refreshedTo) {
          const done = await o.onRefresh();
          if (stopped) return;
          if (done !== false) {
            refreshedTo = v;
          }
        }
      } else {
        await o.onRefresh();
        if (stopped) return;
      }
      lastRunAt = o.now();
      scheduleNormal();
    } catch (e) {
      if (stopped) return;
      if (!handleError(e)) {
        scheduleNormal();
      }
    } finally {
      inFlight = false;
    }
  };

  const onVisibilityChange = () => {
    if (stopped) return;
    if (o.doc.visibilityState === "hidden") {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
      return;
    }

    const now = o.now();
    const elapsed = now - lastRunAt;
    if (elapsed >= periodMs) {
      void tick();
    } else {
      schedule(periodMs - elapsed);
    }
  };

  o.doc.addEventListener("visibilitychange", onVisibilityChange);

  // First tick happens after P (the page has just loaded the data)
  schedule(periodMs);

  return () => {
    stopped = true;
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    o.doc.removeEventListener("visibilitychange", onVisibilityChange);
  };
}

export function useAutoRefresh(o: {
  reportId: string;
  mode: AutoRefreshMode;
  currentVersion: string | null;
  onRefresh: () => Promise<boolean | void>;
}): { status: AutoRefreshStatus | "off" } {
  const { reportId, mode, currentVersion, onRefresh } = o;
  const [status, setStatus] = useState<AutoRefreshStatus | "off">("off");

  const currentVersionRef = useRef(currentVersion);
  currentVersionRef.current = currentVersion;

  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  const onStatusRef = useRef<(s: AutoRefreshStatus) => void>(() => {});
  onStatusRef.current = (s) => setStatus(s);

  useEffect(() => {
    if (mode === "off") {
      setStatus("off");
      return;
    }

    setStatus("ok");

    const stop = startAutoRefresh({
      mode,
      fetchVersion: () =>
        api
          .get<{ data_version: string; updated_at: string | null }>(
            `/api/reports/${encodeURIComponent(reportId)}/version`,
          )
          .then((r) => r.data_version),
      knownVersion: () => currentVersionRef.current,
      onRefresh: () => onRefreshRef.current(),
      onStatus: (s) => onStatusRef.current(s),
    });

    return stop;
  }, [reportId, mode]);

  return { status };
}
