import { Archive, ChevronRight, History, Loader2, Search, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { api } from "../../api/client";
import type { AssistantSession, AssistantSessionSummary } from "../../api/types";
import { t as live, useT } from "../../i18n";
import { dateTimeFormat } from "../../lib/intl";
import { Badge } from "../Badge";
import { ModePill } from "./ModeSelector";
import { useAssistantPanelOptional } from "./AssistantPanelContext";
import { EditableTitle } from "./EditableTitle";

const ICON_BUTTON =
  "inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl text-ink-muted hover:bg-subtle hover:text-ink";

/** Short relative time for the session list ("ahora"/"now", "5 min", "3 h", "2 d", "4 sept"). */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const date = new Date(iso).getTime();
  const minutes = Math.floor(Math.max(0, now - date) / 60_000);
  if (minutes < 1) return live.assistant.justNow;
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} d`;
  return dateTimeFormat({ day: "numeric", month: "short" }).format(new Date(date));
}

type LoadState =
  | { status: "loading" }
  | { status: "ok"; sessions: AssistantSessionSummary[] }
  | { status: "error" };

/** Conversations button + popover (search, recent first, archive, archived group), like the
 * session list of an editor's AI chat. A popover, not a modal: Esc or a click outside closes it. */
export function AssistantHistory({
  currentId,
  onSelect,
  onNew,
  onRenamed,
}: {
  currentId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onRenamed?: (session: AssistantSession) => void;
}) {
  const t = useT();
  const panel = useAssistantPanelOptional();
  // The list follows the panel's width (it is resizable now): a fixed width either truncates the
  // title or leaves the list floating in the middle of a wide chat.
  const popoverWidth = Math.max(340, Math.min((panel?.width ?? 544) - 40, 520));
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [query, setQuery] = useState("");
  const [archivedOpen, setArchivedOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const popoverId = "assistant-history-popover";

  const load = async () => {
    setState({ status: "loading" });
    try {
      const data = await api.get<{ sessions: AssistantSessionSummary[] }>("/api/assistant/sessions");
      setState({ status: "ok", sessions: data.sessions });
    } catch {
      setState({ status: "error" });
    }
  };

  useEffect(() => {
    if (!open) {
      setQuery("");
      setArchivedOpen(false);
      return;
    }
    void load();
    inputRef.current?.focus();
    const onMouseDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  // Esc closes only the popover (stopped here, so the panel around it stays open).
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape" && open) {
      e.stopPropagation();
      setOpen(false);
      buttonRef.current?.focus();
    }
  };

  const sessions = state.status === "ok" ? state.sessions : [];
  const needle = query.trim().toLowerCase();
  const matches = (s: AssistantSessionSummary) => !needle || s.title.toLowerCase().includes(needle);
  const active = sessions.filter((s) => s.status !== "archived");
  const archived = sessions.filter((s) => s.status === "archived");
  const shownActive = active.filter(matches);
  const shownArchived = archived.filter(matches);

  const select = (id: number) => {
    onSelect(id);
    setOpen(false);
  };

  const renamed = (updated: AssistantSession) => {
    setState((prev) => {
      if (prev.status !== "ok") return prev;
      return {
        ...prev,
        sessions: prev.sessions.map((s) =>
          s.id === updated.id ? { ...s, title: updated.title } : s,
        ),
      };
    });
    onRenamed?.(updated);
  };

  const remove = async (s: AssistantSessionSummary) => {
    if (!window.confirm(t.assistant.deleteConfirm(s.title))) return;
    try {
      await api.del(`/api/assistant/sessions/${s.id}`);
      if (s.id === currentId) onNew();
    } finally {
      await load();
    }
  };

  const archive = async (s: AssistantSessionSummary) => {
    try {
      await api.post(`/api/assistant/sessions/${s.id}/archive`);
      if (s.id === currentId) onNew();
    } finally {
      await load();
    }
  };

  const rowClass = (current: boolean) =>
    `flex min-h-tap min-w-0 flex-1 items-center gap-2 rounded-xl px-3 text-left text-sm hover:bg-subtle ${
      current ? "bg-subtle font-semibold text-ink" : "text-ink-2"
    }`;

  const row = (s: AssistantSessionSummary) => (
    <button type="button" className={rowClass(s.id === currentId)} onClick={() => select(s.id)}
      aria-current={s.id === currentId ? "true" : undefined}>
      <span className="min-w-0 flex-1 truncate">{s.title}</span>
      {s.mode === "auto" ? (
        <ModePill session={s} className="shrink-0" />
      ) : null}
      {s.busy ? (
        <Badge tone="accent" icon={<Loader2 className="h-3 w-3 animate-spin" aria-hidden />} className="shrink-0">
          {t.assistant.busyBadge}
        </Badge>
      ) : null}
      <span className="shrink-0 text-xs tabular-nums text-ink-muted">{relativeTime(s.updated_at)}</span>
    </button>
  );

  return (
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      <button
        ref={buttonRef}
        type="button"
        className={ICON_BUTTON}
        onClick={() => setOpen((v) => !v)}
        aria-label={t.assistant.history}
        title={t.assistant.history}
        aria-expanded={open}
        aria-haspopup="true"
        aria-controls={popoverId}
      >
        <History className="h-5 w-5" aria-hidden />
      </button>
      {open ? (
        <div
          id={popoverId}
          /* Wide enough for the title, the mode pill and the time on one line: with the old
             20 rem the title truncated to nothing (owner, 2026-10-21: "make more room to
             history"). The width follows the resizable panel. */
          style={{ width: popoverWidth }}
          className="absolute right-0 top-full z-50 mt-1 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl bg-surface shadow-raised ring-1 ring-line"
        >
          <div className="relative border-b border-line p-3">
            <label className="sr-only" htmlFor="assistant-history-search">
              {t.assistant.searchSessions}
            </label>
            <Search className="pointer-events-none absolute left-6 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" aria-hidden />
            <input
              ref={inputRef}
              id="assistant-history-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.assistant.searchPlaceholder}
              className="w-full rounded-xl border-0 bg-field py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-field-focus"
            />
          </div>

          <div className="max-h-[min(72vh,34rem)] overflow-y-auto p-2">
            {state.status === "loading" ? (
              <p className="px-3 py-2 text-sm text-ink-muted">{t.common.loading}</p>
            ) : state.status === "error" ? (
              <p className="px-3 py-2 text-sm text-ink-muted">{t.assistant.failedToLoadSessions}</p>
            ) : (
              <>
                {shownActive.length === 0 ? (
                  <p className="px-3 py-2 text-sm text-ink-muted">{t.assistant.emptySessions}</p>
                ) : (
                  <ul>
                    {shownActive.map((s) => (
                      <li key={s.id} className="flex items-center gap-1">
                        <EditableTitle
                          sessionId={s.id}
                          title={s.title}
                          onRenamed={renamed}
                          className="min-w-0 flex-1"
                          buttonLabel={`${t.assistant.rename} ${s.title}`}
                        >
                          {row(s)}
                        </EditableTitle>
                        <button
                          type="button"
                          className={`${ICON_BUTTON} disabled:cursor-not-allowed disabled:opacity-50`}
                          aria-label={`${t.assistant.archive} ${s.title}`}
                          title={t.assistant.archive}
                          disabled={s.busy}
                          onClick={() => void archive(s)}
                        >
                          <Archive className="h-4 w-4" aria-hidden />
                        </button>
                        <button
                          type="button"
                          className={`${ICON_BUTTON} disabled:cursor-not-allowed disabled:opacity-50`}
                          aria-label={`${t.assistant.deleteSession} ${s.title}`}
                          title={t.assistant.deleteSession}
                          disabled={s.busy}
                          onClick={() => void remove(s)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {archived.length > 0 ? (
                  <div className="mt-2 border-t border-line pt-2">
                    <button
                      type="button"
                      className="flex min-h-tap w-full items-center gap-2 rounded-xl px-3 text-left text-sm text-ink-2 hover:bg-subtle"
                      onClick={() => setArchivedOpen((v) => !v)}
                      aria-expanded={archivedOpen}
                    >
                      <ChevronRight
                        className={`h-4 w-4 shrink-0 text-ink-muted transition-transform motion-reduce:transition-none ${archivedOpen ? "rotate-90" : ""}`}
                        aria-hidden
                      />
                      <span className="flex-1">{t.assistant.archivedSessions}</span>
                      <span className="rounded-full bg-subtle px-2 text-xs text-ink-2">{archived.length}</span>
                    </button>
                    {archivedOpen ? (
                      <ul className="mt-1">
                        {shownArchived.map((s) => (
                          <li key={s.id} className="flex items-center gap-1">
                            <EditableTitle
                              sessionId={s.id}
                              title={s.title}
                              onRenamed={renamed}
                              className="min-w-0 flex-1"
                              buttonLabel={`${t.assistant.rename} ${s.title}`}
                            >
                              {row(s)}
                            </EditableTitle>
                            {/* Archived chats are the ones that pile up: they must be removable. */}
                            <button
                              type="button"
                              className={`${ICON_BUTTON} disabled:cursor-not-allowed disabled:opacity-50`}
                              aria-label={`${t.assistant.deleteSession} ${s.title}`}
                              title={t.assistant.deleteSession}
                              disabled={s.busy}
                              onClick={() => void remove(s)}
                            >
                              <Trash2 className="h-4 w-4" aria-hidden />
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
