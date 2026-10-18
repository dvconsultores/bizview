import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useBranding } from "../config/BrandingContext";
import { es, type Catalogue } from "./es";
export type { Catalogue } from "./es";
export type { Locale, LocalePreference } from "./resolve";
export { intlTag } from "./resolve";
import { intlTag, LOCALE_STORAGE_KEY, normalizeLocale, resolveLocale, type Locale, type LocalePreference } from "./resolve";
import { activate, CATALOGUES } from "./live";
export { t, currentLocale, currentIntlTag, activate } from "./live";
export { rich } from "./rich";

/* Feature 022: UI language catalogue with live, imperative and React bindings. */

function browserLanguages(): readonly string[] {
  if (typeof navigator === "undefined") return [];
  return navigator.languages ?? [];
}

function readDeviceLocale(): Locale | null {
  try {
    return normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY));
  } catch {
    return null;
  }
}

function writeDeviceLocale(pref: LocalePreference) {
  try {
    if (pref) localStorage.setItem(LOCALE_STORAGE_KEY, pref);
    else localStorage.removeItem(LOCALE_STORAGE_KEY);
  } catch {
    // storage blocked: the in-memory preference still applies for this session
  }
}

export interface LocaleState {
  locale: Locale;
  preference: LocalePreference;
  intlTag: string;
  t: Catalogue;
  setPreference: (p: LocalePreference) => Promise<void>;
}

const LocaleContext = createContext<LocaleState>({
  locale: "es",
  preference: null,
  intlTag: "es-ES",
  t: es,
  setPreference: async () => {},
});

// Owns the UI language; resolution account → device → browser → DEFAULT_LOCALE (FR-002).
// <html lang> follows it (FR-011). A device choice is saved once to an account whose locale is still null (US1 AC3).
export function LocaleProvider({ children }: { children: ReactNode }) {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const { default_locale } = useBranding();
  const [preference, setPref] = useState<LocalePreference>(readDeviceLocale);
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve());
  const latestSave = useRef(0);
  const syncedUserId = useRef<number | null>(null);
  const locale = resolveLocale({
    account: preference,
    languages: browserLanguages(),
    defaultLocale: default_locale,
  });
  // Sync the live binding before children render.
  activate(locale);

  useLayoutEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const accountLocale = user?.locale;
  useEffect(() => {
    if (accountLocale !== "es" && accountLocale !== "en") return;
    setPref(accountLocale);
    writeDeviceLocale(accountLocale);
  }, [accountLocale]);

  const save = useCallback(
    async (p: LocalePreference, u: NonNullable<typeof user>) => {
      const id = ++latestSave.current;
      const saveOp = saveQueue.current.then(() =>
        api.patch<{ locale: LocalePreference }>("/api/me/preferences", { locale: p }),
      );
      saveQueue.current = saveOp.catch(() => undefined);
      try {
        const saved = await saveOp;
        if (id !== latestSave.current) return;
        setUser({ ...u, locale: saved.locale });
      } catch {
        if (id !== latestSave.current) return;
        // Like the theme: the applied language is kept even if saving failed.
        const applied = resolveLocale({
          account: p,
          languages: browserLanguages(),
          defaultLocale: default_locale,
        });
        toast(CATALOGUES[applied].language.saveFailed, "warning");
      }
    },
    [default_locale, setUser, toast],
  );

  useEffect(() => {
    if (!user || user.locale !== null || syncedUserId.current === user.id) return;
    const device = readDeviceLocale();
    if (!device) return;
    syncedUserId.current = user.id;
    void save(device, user);
  }, [save, user]);

  const setPreference = useCallback(
    async (p: LocalePreference) => {
      setPref(p);
      writeDeviceLocale(p);
      if (!user) return;
      await save(p, user);
    },
    [save, user],
  );

  const value = useMemo<LocaleState>(
    () => ({
      locale,
      preference,
      intlTag: intlTag(locale),
      t: CATALOGUES[locale],
      setPreference,
    }),
    [locale, preference, setPreference],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useT(): Catalogue {
  return useContext(LocaleContext).t;
}

export function useLocale(): LocaleState {
  return useContext(LocaleContext);
}
