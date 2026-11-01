import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { useBranding } from "../config/BrandingContext";
import { useT } from "../i18n";
import { knownTheme, loadTheme, reportThemeId } from "./library";
import { applyThemeVariables } from "./palette";
import { BUILTIN_THEMES, type Theme } from "./themes";
import {
  applyTheme, darkQuery, readCachedPreference, resolveTheme, systemPrefersDark, writeCachedPreference,
  type ResolvedTheme, type ThemePreference,
} from "./resolve";

interface ThemeState {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  /** Applies at once on this device, then saves to the account when signed in (FR-003, FR-004). */
  setPreference: (p: ThemePreference) => Promise<void>;
  /** Feature 030/047: the theme in force (report override → installation → `impacto`). */
  palette: string;
  /** The tokens of the theme in force, so a page can scope them to its own area (047 FR-019). */
  tokens: Theme;
  /** Feature 030: the page's own theme override (`layout.theme.id`, or its deprecated alias
   * `palette`); `null` uses the installation's. */
  setPalette: (preset: string | null) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

/** Owns the theme after /theme-init.js set the first one. Before sign-in the device cache and the
 * device appearance decide (FR-007); once the user is known their account value wins. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const t = useT();
  const { user, setUser } = useAuth();
  const toast = useToast();
  const branding = useBranding();
  const [preference, setPref] = useState<ThemePreference>(readCachedPreference);
  const [prefersDark, setPrefersDark] = useState(systemPrefersDark);
  const resolved = resolveTheme(preference, prefersDark);
  const [override, setPaletteOverride] = useState<string | null>(null);
  const palette = reportThemeId(
    override ? { id: override } : null,
    branding.theme_id ?? branding.palette_preset,
  );
  // The theme's own tokens: a built-in is in this build, an uploaded one arrives from the server.
  // Until it does the page keeps the default's colours rather than flashing unthemed.
  const [tokens, setTokens] = useState(() => knownTheme(palette) ?? BUILTIN_THEMES.impacto);
  useEffect(() => {
    let cancelled = false;
    const immediate = knownTheme(palette);
    if (immediate) {
      setTokens(immediate);
      return;
    }
    void loadTheme(palette).then((theme) => {
      if (!cancelled && theme) setTokens(theme);
    });
    return () => {
      cancelled = true;
    };
  }, [palette]);

  // Saves run one after another so the account ends on the last choice, and only the last
  // response updates the screen (out-of-order PATCHes cannot make an older choice win).
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve());
  const latestSave = useRef(0);

  useEffect(() => applyTheme(resolved), [resolved]);

  // Feature 030: the theme follows the choice and the resolved mode, and its shape tokens travel
  // with it (047); the shared view and the report page re-theme with no reload.
  useEffect(() => applyThemeVariables(tokens, resolved, palette), [tokens, palette, resolved]);
  const setPalette = useCallback((preset: string | null) => setPaletteOverride(preset), []);

  // Follow the device appearance while open (FR-005). addListener: Safari 14.
  useEffect(() => {
    const mq = darkQuery();
    if (!mq) return;
    const onChange = () => setPrefersDark(mq.matches);
    if (mq.addEventListener) mq.addEventListener("change", onChange);
    else mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener("change", onChange);
      else mq.removeListener(onChange);
    };
  }, []);

  // The account value wins over the device cache (sign-in, /api/me).
  const accountTheme = user?.theme;
  useEffect(() => {
    if (!accountTheme) return;
    setPref(accountTheme);
    writeCachedPreference(accountTheme);
  }, [accountTheme]);

  const setPreference = useCallback(async (p: ThemePreference) => {
    setPref(p);
    writeCachedPreference(p);
    if (!user) return;
    const id = ++latestSave.current;
    const save = saveQueue.current.then(() =>
      api.patch<{ theme: ThemePreference }>("/api/me/preferences", { theme: p })
    );
    saveQueue.current = save.catch(() => undefined);
    try {
      const saved = await save;
      if (id !== latestSave.current) return;
      setUser({ ...user, theme: saved.theme });
    } catch {
      if (id !== latestSave.current) return;
      toast(t.theme.saveFailed, "warning");   // FR-013: keep the applied theme
    }
  }, [user, setUser, toast, t]);

  const value = useMemo(
    () => ({ preference, resolved, setPreference, palette, tokens, setPalette }),
    [preference, resolved, setPreference, palette, tokens, setPalette],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme outside ThemeProvider");
  return ctx;
}
