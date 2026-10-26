import { useEffect, useState } from "react";
import type { AIHealth } from "../api/types";
import { api } from "./client";

/**
 * The installation's AI health, read from `/api/health` (feature 035).
 *
 * One request, shared by the composer pill and the administration home: while the provider is
 * unhealthy the reader sees it before typing, instead of after a dead turn.
 */
export function useAIHealth(refreshMs = 60_000): AIHealth | null {
  const [health, setHealth] = useState<AIHealth | null>(null);
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      // Health is a nice-to-have: a mocked or unreachable client must not break the composer.
      Promise.resolve()
        .then(() => api.get<{ ai?: AIHealth }>("/api/health"))
        .then((body) => !cancelled && setHealth(body?.ai ?? null))
        .catch(() => !cancelled && setHealth(null));
    };
    load();
    const timer = window.setInterval(load, refreshMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [refreshMs]);
  return health;
}

/** `off` | `ok` | `error`, computed the same way in every consumer. */
export function aiHealthState(health: AIHealth | null): "unknown" | "off" | "ok" | "error" {
  if (!health) return "unknown";
  if (!health.configured) return "off";
  if (!health.last_error_code) return "ok";
  if (health.last_ok_at && (!health.last_error_at || health.last_ok_at >= health.last_error_at)) {
    return "ok";
  }
  return "error";
}
