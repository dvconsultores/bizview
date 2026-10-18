import type { AssistantSession } from "../../api/types";
import { useT } from "../../i18n";
import { formatValue } from "../../lib/numbers";
import { Alert } from "../Alert";

export function BudgetNotice({ session }: { session: AssistantSession }) {
  const t = useT();
  if (session.status === "archived") return null;

  const limit = Math.max(session.token_budget || 0, session.budget_max ?? 0);
  const exhausted = limit > 0 && session.tokens_used >= limit;

  if (!exhausted && !session.budget_warning) return null;

  const pct = Math.min(100, Math.floor((session.tokens_used * 100) / limit));

  return (
    <div data-budget-notice="" {...(exhausted ? { "data-budget-max": "" } : {})}>
      {exhausted ? (
        <Alert tone="warning">{t.assistant.budgetMaxReached}</Alert>
      ) : (
        <Alert tone="warning">
          {t.assistant.budgetWarning
            .replace("{pct}", String(pct))
            .replace("{used}", formatValue(session.tokens_used, "integer"))
            .replace("{budget}", formatValue(limit, "integer"))}
        </Alert>
      )}
    </div>
  );
}
