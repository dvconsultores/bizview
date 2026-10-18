import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { PublicConfig } from "../api/types";

const DEFAULT: PublicConfig = {
  product_name: "Bizview AI Powered",
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

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PublicConfig>(DEFAULT);
  // Fetched at start; retried every 5 s while the backend is unreachable (otherwise AI-dependent
  // menus stay hidden until a full reload) and refreshed when the tab becomes visible again.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const load = (attempt: number) => {
      window.clearTimeout(timer);
      api
        .get<PublicConfig>("/api/config")
        .then((c) => {
          if (!cancelled) setConfig(c);
        })
        .catch(() => {
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
  }, []);
  useEffect(() => {
    document.title = config.organization_name
      ? `${config.product_name} · ${config.organization_name}`
      : config.product_name;
  }, [config]);
  return <BrandingContext.Provider value={config}>{children}</BrandingContext.Provider>;
}

export const useBranding = () => useContext(BrandingContext);
