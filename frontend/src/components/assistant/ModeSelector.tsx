import { useRef } from "react";
import type { AssistantMode, AssistantSession } from "../../api/types";
import { useT } from "../../i18n";

const MODES: AssistantMode[] = ["ask", "edit", "auto"];

/**
 * Feature 028: the mode selector of the composer (FR-000).
 *
 * A segmented control (never a dropdown on phones) above the message box. Switching **down** takes
 * effect at once; switching **up** to Auto asks the parent for a run contract, and the mode only
 * changes when that contract is confirmed.
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
  const mode: AssistantMode = session.mode ?? "edit";
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const labels: Record<AssistantMode, string> = {
    ask: t.assistant.modes.ask,
    edit: t.assistant.modes.edit,
    auto: t.assistant.modes.auto,
  };
  const hints: Record<AssistantMode, string> = {
    ask: t.assistant.modes.askHint,
    edit: t.assistant.modes.editHint,
    auto: t.assistant.modes.autoHint,
  };

  const choose = (next: AssistantMode, opener: HTMLElement) => {
    if (next === mode) return;
    if (next === "auto") {
      onRequestAuto(opener);
      return;
    }
    onSelect(next);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const index = MODES.indexOf(mode);
    const next = MODES[(index + step + MODES.length) % MODES.length];
    const button = refs.current[next];
    button?.focus();
    if (button) choose(next, button);
  };

  return (
    <div
      role="radiogroup"
      aria-label={t.assistant.modes.label}
      data-mode-selector=""
      onKeyDown={onKeyDown}
      className="inline-flex items-center gap-0.5 rounded-full border border-line bg-surface p-0.5"
    >
      {MODES.map((item) => {
        const active = item === mode;
        return (
          <button
            key={item}
            ref={(node) => {
              refs.current[item] = node;
            }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            disabled={disabled}
            title={hints[item]}
            data-mode={item}
            onClick={(event) => choose(item, event.currentTarget)}
            className={`inline-flex min-h-tap items-center rounded-full px-3 text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 ${
              active
                ? "bg-accent text-on-primary"
                : "text-ink-2 hover:bg-subtle hover:text-ink"
            }`}
          >
            {labels[item]}
          </button>
        );
      })}
    </div>
  );
}

/** The pill of a conversation: the mode and, in Auto, whether a contract is live (FR-000). */
export function ModePill({
  session,
  className,
}: {
  session: Pick<AssistantSession, "mode" | "contract_status" | "busy">;
  className?: string;
}) {
  const t = useT();
  const mode = session.mode ?? "edit";
  const status = session.contract_status ?? "none";
  const label =
    mode !== "auto"
      ? mode === "ask"
        ? t.assistant.modes.ask
        : t.assistant.modes.edit
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
