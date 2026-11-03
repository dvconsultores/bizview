import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { PublicConfig } from "../api/types";

const DEFAULT: PublicConfig = {
  product_name: "Bizview",
  organization_name: "",
  logo_url: null,
  version: "",
  source_url: null,
  license: "AGPL-3.0-or-later",
  ai_enabled: false,
  telegram_sign_in: false,
  telegram_bot: null,
  google_auth: false,
};
const BrandingContext = createContext<PublicConfig>(DEFAULT);
/** Feature 051: re-read the config so a change made here reaches every mounted page at once. */
const RefreshContext = createContext<() => Promise<void>>(async () => undefined);

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PublicConfig>(DEFAULT);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /** One read of `/api/config`; rejects so a caller that needs the new value can await it. */
  const read = useCallback(async () => {
    const next = await api.get<PublicConfig>("/api/config");
    if (mounted.current) setConfig(next);
  }, []);
  const refresh = useCallback(async () => {
    try {
      await read();
    } catch {
      /* the caller reports it; the page keeps the theme it has */
    }
  }, [read]);

  // Fetched at start; retried every 5 s while the backend is unreachable (otherwise AI-dependent
  // menus stay hidden until a full reload) and refreshed when the tab becomes visible again.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const load = (attempt: number) => {
      window.clearTimeout(timer);
      read().catch(() => {
        if (!cancelled && attempt < 60) timer = window.setTimeout(() => load(attempt + 1), 5000);
      });
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") load(0);
    };
    load(0);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [read]);
  useEffect(() => {
    document.title = config.organization_name
      ? `${config.product_name} · ${config.organization_name}`
      : config.product_name;
  }, [config]);
  return (
    <RefreshContext.Provider value={refresh}>
      <BrandingContext.Provider value={config}>{children}</BrandingContext.Provider>
    </RefreshContext.Provider>
  );
}

export const useBranding = () => useContext(BrandingContext);
export const useBrandingRefresh = () => useContext(RefreshContext);
