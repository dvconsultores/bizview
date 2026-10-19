import type { AssistantSession } from "../../api/types";
import { useT } from "../../i18n";
import { formatValue } from "../../lib/numbers";
import { Alert } from "../Alert";

export function BudgetNotice(props: {
  session: AssistantSession;
  onExtend?: () => void;
  extending?: boolean;
}) {
  const { session } = props;
  const t = useT();
  if (session.status === "archived") return null;

  const limit = Math.max(session.token_budget || 0, session.budget_max ?? 0);
  const exhausted = limit > 0 && session.tokens_used >= limit;

  if (!exhausted && !session.budget_warning) return null;

  const pct = Math.min(100, Math.floor((session.tokens_used * 100) / limit));
  // The server refuses past `budget_max`, so the button disappears at the ceiling.
  const canExtend = !!props.onExtend && (session.token_budget ?? 0) < (session.budget_max ?? 0);

  return (
    <div data-budget-notice="" {...(exhausted ? { "data-budget-max": "" } : {})}>
      <Alert tone="warning">
        <span className="flex flex-col gap-2">
          {exhausted ? t.assistant.budgetMaxReached : t.assistant.budgetWarning
            .replace("{pct}", String(pct))
            .replace("{used}", formatValue(session.tokens_used, "integer"))
            .replace("{budget}", formatValue(limit, "integer"))}
          {canExtend ? (
            <span>
              <button
                type="button"
                data-extend-budget=""
                onClick={props.onExtend}
                disabled={props.extending}
                className="inline-flex min-h-tap items-center rounded-lg border border-line px-3 text-sm text-ink hover:border-line-strong disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                {props.extending ? t.assistant.extending : t.assistant.extendBudget}
              </button>
            </span>
          ) : exhausted ? (
            <span className="text-sm">{t.assistant.budgetCapped}</span>
          ) : null}
        </span>
      </Alert>
    </div>
  );
}
