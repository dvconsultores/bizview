import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, MessageSquare, Zap } from "lucide-react";
import type { AssistantMode, AssistantSession } from "../../api/types";
import { useT } from "../../i18n";

/** The two modes of the composer (feature 028): ask and auto. `edit` is legacy state only. */
const MODES: AssistantMode[] = ["ask", "auto"];

/**
 * Feature 028, simplified on the owner's request: one compact button that opens a short menu
 * (name + one line each), like the mode picker of other agents. Two choices only:
 *
 * - **Preguntar**: reads and explains, writes nothing.
 * - **Auto**: runs the whole pipeline and applies, once the run is authorised.
 *
 * Choosing Auto does not switch the mode by itself: the parent asks for the run confirmation and
 * the mode changes when that is accepted.
 */
export function ModeSelector({
  session,
  disabled,
  onSelect,
  onRequestAuto,
}: {
  session: AssistantSession;
  disabled?: boolean;
  onSelect: (mode: AssistantMode) => void;
  onRequestAuto: (opener: HTMLElement) => void;
}) {
  const t = useT();
  const mode: AssistantMode = session.mode ?? "auto";
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const copy: Record<AssistantMode, { name: string; description: string }> = {
    ask: { name: t.assistant.modes.ask, description: t.assistant.modes.askHint },
    edit: { name: t.assistant.modes.edit, description: t.assistant.modes.editHint },
    auto: { name: t.assistant.modes.auto, description: t.assistant.modes.autoHint },
  };
  const current = copy[mode] ?? copy.auto;

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const choose = (next: AssistantMode, opener: HTMLElement) => {
    setOpen(false);
    if (next === mode) return;
    if (next === "auto") {
      onRequestAuto(opener);
      return;
    }
    onSelect(next);
  };

  const focusItem = (index: number) => {
    const items = rootRef.current?.querySelectorAll<HTMLElement>("[data-mode-option]");
    items?.[(index + items.length) % items.length]?.focus();
  };

  return (
    <div ref={rootRef} className="relative inline-flex" data-mode-selector="">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${t.assistant.modes.label}: ${current.name}`}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex min-h-tap items-center gap-1.5 rounded-full border border-line bg-surface px-3 text-xs font-medium text-ink-2 hover:border-line-strong hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
      >
        <ModeIcon mode={mode} />
        {current.name}
        <ChevronDown className="h-3.5 w-3.5" aria-hidden />
      </button>

      {open ? (
        <div
          role="menu"
          aria-label={t.assistant.modes.label}
          data-mode-menu=""
          className="absolute bottom-full left-0 z-20 mb-2 w-72 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-lg"
        >
          {MODES.map((item, index) => {
            const active = item === mode;
            return (
              <button
                key={item}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                data-mode-option={item}
                onClick={(event) => choose(item, event.currentTarget)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    focusItem(index + 1);
                  } else if (event.key === "ArrowUp") {
                    event.preventDefault();
                    focusItem(index - 1);
                  } else if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    choose(item, event.currentTarget);
                  }
                }}
                className={`flex w-full items-start gap-2.5 px-3 py-2 text-left hover:bg-subtle focus-visible:bg-subtle focus-visible:outline-none ${
                  active ? "text-ink" : "text-ink-2"
                }`}
              >
                <ModeIcon mode={item} className="mt-0.5 h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{copy[item].name}</span>
                  <span className="mt-0.5 block text-xs text-ink-muted">
                    {copy[item].description}
                  </span>
                </span>
                {active ? (
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function ModeIcon({ mode, className }: { mode: AssistantMode; className?: string }) {
  const Icon = mode === "ask" ? MessageSquare : Zap;
  return <Icon className={className ?? "h-3.5 w-3.5"} aria-hidden />;
}

/** The pill of a conversation: the mode and, in Auto, whether a run is authorised (FR-000). */
export function ModePill({
  session,
  className,
}: {
  session: Pick<AssistantSession, "mode" | "contract_status" | "busy">;
  className?: string;
}) {
  const t = useT();
  const mode = session.mode ?? "auto";
  const status = session.contract_status ?? "none";
  const label =
    mode === "ask"
      ? t.assistant.modes.ask
      : mode === "edit"
        ? t.assistant.modes.edit
        : status === "running" && session.busy
          ? t.assistant.pill.running
          : status === "applied"
            ? t.assistant.pill.applied
            : status === "failed"
              ? t.assistant.pill.failed
              : status === "stopped"
                ? t.assistant.pill.stopped
                : t.assistant.pill.none;
  const live = mode === "auto" && (status === "confirmed" || status === "running");
  return (
    <span
      data-mode-pill=""
      data-tone={live ? "auto" : "muted"}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
        live
          ? "border-accent/40 bg-accent-soft text-accent"
          : "border-line bg-surface text-ink-2"
      } ${className ?? ""}`}
    >
      {label}
    </span>
  );
}
