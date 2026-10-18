import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

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
  /** Text waiting to be placed in the composer (023: "Preguntar al asistente"). */
  draft: string | null;
  openWith(text: string): void;
  takeDraft(): string | null;
}

const MODE_KEY = "bizview.assistantPanel.mode";
const SESSION_KEY = "bizview.assistantPanel.session";

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

  const setMode = useCallback((next: PanelMode) => {
    setModeState(next);
    write(MODE_KEY, next);
  }, []);
  const open = useCallback(() => setMode(mode === "expanded" ? "expanded" : "docked"), [mode, setMode]);
  const close = useCallback(() => setMode("closed"), [setMode]);
  const toggle = useCallback(() => setMode(mode === "closed" ? "docked" : "closed"), [mode, setMode]);
  const setExpanded = useCallback((e: boolean) => setMode(e ? "expanded" : "docked"), [setMode]);
  const setSessionId = useCallback((id: number | null) => {
    setSessionState(id);
    write(SESSION_KEY, id === null ? null : String(id));
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
    () => ({ mode, sessionId, open, close, toggle, setExpanded, setSessionId, draft, openWith, takeDraft }),
    [mode, sessionId, open, close, toggle, setExpanded, setSessionId, draft, openWith, takeDraft],
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
