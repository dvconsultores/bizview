import {
  createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode,
} from "react";

/** Docked assistant panel state (Customer A-style): remembered per device. */
export type PanelMode = "closed" | "docked" | "expanded";

interface AssistantPanelState {
  mode: PanelMode;
  sessionId: number | null;
  open(): void;
  close(): void;
  toggle(): void;
  setExpanded(expanded: boolean): void;
  setSessionId(id: number | null): void;
  /** Width of the docked panel in px (owner, 2026-10-21: resizable like VS Code). */
  width: number;
  setWidth(px: number): void;
  /** Text waiting to be placed in the composer (023: "Preguntar al asistente"). */
  draft: string | null;
  openWith(text: string): void;
  takeDraft(): string | null;
}

const MODE_KEY = "bizview.assistantPanel.mode";
const SESSION_KEY = "bizview.assistantPanel.session";
const WIDTH_KEY = "bizview.assistantPanel.width";

/** The docked panel starts at the width it had before feature 014 narrowed it (34 rem) and can be
 * dragged from 22 rem to 60 rem, never past 70 % of the screen. */
export const PANEL_WIDTH = { min: 352, max: 960, default: 544 };
export const PANEL_WIDTH_MAX_RATIO = 0.7;

export function clampPanelWidth(px: number, viewport?: number): number {
  const screen = viewport ?? (typeof window === "undefined" ? 1440 : window.innerWidth);
  const max = Math.min(PANEL_WIDTH.max, Math.round(screen * PANEL_WIDTH_MAX_RATIO));
  return Math.max(PANEL_WIDTH.min, Math.min(Math.round(px), max));
}

function storedWidth(): number {
  const px = Number(read(WIDTH_KEY));
  return Number.isFinite(px) && px > 0 ? clampPanelWidth(px) : PANEL_WIDTH.default;
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the state still works for this page */
  }
}

function storedMode(): PanelMode {
  const raw = read(MODE_KEY);
  return raw === "docked" || raw === "expanded" ? raw : "closed";
}

function storedSession(): number | null {
  const id = Number(read(SESSION_KEY));
  return Number.isInteger(id) && id > 0 ? id : null;
}

const Ctx = createContext<AssistantPanelState | null>(null);

export function AssistantPanelProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<PanelMode>(storedMode);
  const [sessionId, setSessionState] = useState<number | null>(storedSession);
  const [draft, setDraft] = useState<string | null>(null);
  const [width, setWidthState] = useState<number>(storedWidth);

  const setMode = useCallback((next: PanelMode) => {
    setModeState(next);
    write(MODE_KEY, next);
  }, []);
  const open = useCallback(() => setMode(mode === "expanded" ? "expanded" : "docked"), [mode, setMode]);
  const close = useCallback(() => setMode("closed"), [setMode]);
  const toggle = useCallback(() => setMode(mode === "closed" ? "docked" : "closed"), [mode, setMode]);
  const setExpanded = useCallback((e: boolean) => setMode(e ? "expanded" : "docked"), [setMode]);
  const setWidth = useCallback((px: number) => {
    const next = clampPanelWidth(px);
    setWidthState(next);
    write(WIDTH_KEY, String(next));
  }, []);
  const setSessionId = useCallback((id: number | null) => {
    setSessionState(id);
    write(SESSION_KEY, id === null ? null : String(id));
  }, []);

  // A narrower window must not leave the panel wider than the screen allows (it is remembered in
  // px): re-clamped on resize, without touching what the person chose.
  useEffect(() => {
    const onResize = () => setWidthState((current) => clampPanelWidth(current));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const openWith = useCallback((text: string) => {
    setDraft(text);
    open();
  }, [open]);
  const takeDraft = useCallback(() => {
    const text = draft;
    if (text !== null) setDraft(null);
    return text;
  }, [draft]);

  const value = useMemo(
    () => ({ mode, sessionId, width, setWidth, open, close, toggle, setExpanded, setSessionId,
             draft, openWith, takeDraft }),
    [mode, sessionId, width, setWidth, open, close, toggle, setExpanded, setSessionId, draft,
     openWith, takeDraft],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** The panel state, or null where the chat is rendered outside the shell. */
export function useAssistantPanelOptional(): AssistantPanelState | null {
  return useContext(Ctx);
}

export function useAssistantPanel(): AssistantPanelState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAssistantPanel must be used within AssistantPanelProvider");
  return ctx;
}
