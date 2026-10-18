import type { AssistantSession } from "../../api/types";
import { t, useT } from "../../i18n";

export type SessionIndicatorState = "working" | "no_budget" | "ready";

export function sessionIndicator(
  session: Pick<AssistantSession, "busy" | "tokens_used" | "token_budget" | "budget_max" | "model">,
  workingOverride?: boolean,
): {
  state: SessionIndicatorState;
  label: string;
  model: string | null;
  budgetText: string;
  ariaLabel: string;
} {
  const busy = !!session.busy || !!workingOverride;
  const budget = Math.max(session.token_budget || 0, session.budget_max ?? 0);
  const over = budget <= 0 || session.tokens_used > budget;
  const noBudget = budget <= 0 || session.tokens_used >= budget;
  const state: SessionIndicatorState = busy ? "working" : noBudget ? "no_budget" : "ready";
  const label =
    state === "working"
      ? t.assistant.sessionIndicator.working
      : state === "no_budget"
        ? t.assistant.sessionIndicator.noBudget
        : t.assistant.sessionIndicator.ready;
  const budgetText = over ? "100 %+" : `${Math.floor((session.tokens_used * 100) / budget)} %`;
  const model = session.model ?? null;
  const ariaLabel = model
    ? t.assistant.sessionIndicator.ariaLabel
        .replace("{label}", label)
        .replace("{model}", model)
        .replace("{pct}", budgetText)
    : t.assistant.sessionIndicator.ariaLabelNoModel
        .replace("{label}", label)
        .replace("{pct}", budgetText);
  return { state, label, model, budgetText, ariaLabel };
}

export function SessionIndicator(props: {
  session: AssistantSession;
  working?: boolean;
  className?: string;
  onOpen?: (opener: HTMLElement) => void;
}) {
  const t = useT();
  const { session, working, className, onOpen } = props;
  const { state, label, model, budgetText, ariaLabel } = sessionIndicator(session, working);
  const dotClass =
    state === "working" ? "bg-accent" : state === "no_budget" ? "bg-warning" : "bg-success";
  const inner = (
    <span
      role="status"
      data-session-indicator=""
      aria-label={ariaLabel}
      className={`inline-flex min-w-0 max-w-full shrink items-center gap-1.5 overflow-hidden whitespace-nowrap rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-ink-2 ${onOpen ? "hover:border-line-strong" : ""} ${className ?? ""}`}
    >
      <span className="relative inline-flex h-2 w-2 shrink-0">
        {state === "working" ? (
          <span
            className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-75 motion-safe:animate-ping"
            aria-hidden
          />
        ) : null}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${dotClass}`} />
      </span>
      <span className="min-w-0 truncate">{label}</span>
      {model ? (
        <>
          <span className="hidden text-ink-muted sm:inline" aria-hidden>
            ·
          </span>
          <span
            className="hidden min-w-0 max-w-[6rem] truncate sm:inline sm:max-w-[10rem]"
            title={model}
          >
            {model}
          </span>
        </>
      ) : null}
      <span className="text-ink-muted" aria-hidden>
        ·
      </span>
      <span className="shrink-0">{budgetText}</span>
    </span>
  );
  if (!onOpen) return inner;
  return (
    <button
      type="button"
      onClick={(e) => onOpen(e.currentTarget)}
      title={t.assistant.agentMap.open}
      aria-label={`${t.assistant.agentMap.open}: ${ariaLabel}`}
      data-agent-map-open=""
      className="inline-flex min-h-tap min-w-0 max-w-full shrink items-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      {inner}
    </button>
  );
}
