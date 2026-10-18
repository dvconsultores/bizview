import { CheckCircle2, CircleDashed } from "lucide-react";
import { Badge } from "../Badge";
import type { AssistantPendingItem, AssistantSession } from "../../api/types";
import { t, useT } from "../../i18n";

export interface ReadinessItem {
  key: "validation" | "queries" | "preview";
  label: string;
  ok: boolean;
  messages: string[];
}

function pendingMessages(items: AssistantPendingItem[]): string[] {
  return items.map((item) => (item.file ? `${item.file}: ${item.message}` : item.message));
}

export function readinessItems(session: AssistantSession): {
  items: ReadinessItem[];
  other: AssistantPendingItem[];
  ready: boolean;
} {
  const pending = session.readiness?.pending ?? [];
  const hasDraft = !!session.draft;
  const queriesPending = pending.filter((p) => p.code === "query_check");
  const previewPending = pending.filter((p) => p.code === "preview");
  const other = pending.filter((p) => p.code !== "query_check" && p.code !== "preview" && p.code !== "draft");

  return {
    items: [
      {
        key: "validation",
        label: t.assistant.checkValidation,
        ok: hasDraft && !!session.validation?.valid,
        messages: [],
      },
      {
        key: "queries",
        label: t.assistant.checkQueries,
        ok: hasDraft && queriesPending.length === 0,
        messages: pendingMessages(queriesPending),
      },
      {
        key: "preview",
        label: t.assistant.checkPreview,
        ok: hasDraft && previewPending.length === 0,
        messages: pendingMessages(previewPending),
      },
    ],
    other,
    ready: !!session.readiness?.ready,
  };
}

export function ReadinessPill({ ready }: { ready: boolean }) {
  const t = useT();
  if (ready) {
    return (
      <Badge tone="success" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />}>
        {t.assistant.readyPill}
      </Badge>
    );
  }
  return (
    <Badge tone="neutral" icon={<CircleDashed className="h-3.5 w-3.5" aria-hidden="true" />}>
      {t.assistant.notReadyPill}
    </Badge>
  );
}

export function ReadinessChecklist({ session }: { session: AssistantSession }) {
  const t = useT();
  const { items, other, ready } = readinessItems(session);

  return (
    <section aria-label={t.assistant.readiness} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-base font-semibold text-ink">{t.assistant.readiness}</h4>
        <ReadinessPill ready={ready} />
      </div>
      <ul className="flex flex-col gap-1.5">
        {items.map((item) => (
          <li key={item.key} data-ok={item.ok ? "true" : "false"} className="flex flex-col gap-0.5">
            <div className="flex items-start gap-1.5">
              {item.ok ? (
                <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
              ) : (
                <CircleDashed className="mt-1 h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
              )}
              <span className="text-base text-ink">{item.label}</span>
            </div>
            {item.messages.length > 0 ? (
              <ul className="flex flex-col gap-0.5 pl-[1.375rem]">
                {item.messages.map((message, index) => (
                  <li key={index} className="text-sm text-ink-2">
                    {message}
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
      {other.length > 0 ? (
        <div className="flex flex-col gap-1">
          <h5 className="text-sm font-semibold text-ink-2">{t.assistant.otherPending}</h5>
          <ul className="flex flex-col gap-0.5">
            {pendingMessages(other).map((message, index) => (
              <li key={index} className="text-sm text-ink-2">
                {message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
