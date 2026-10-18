import type { AssistantSession, AssistantWorkingState } from "../../api/types";
import { useT } from "../../i18n";
import { formatValue } from "../../lib/numbers";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function renderStringArray(items: unknown): string[] | null {
  if (!Array.isArray(items)) return null;
  const strings = items.filter((item): item is string => typeof item === "string");
  return strings.length > 0 ? strings : null;
}

function hasContent(ws: AssistantWorkingState | undefined): boolean {
  if (!ws) return false;
  const hasString = (value: unknown): boolean => typeof value === "string" && value.length > 0;
  const hasInspected = (() => {
    if (!isRecord(ws.inspected)) return false;
    return Object.entries(ws.inspected).some(([, entries]) => {
      if (!isRecord(entries)) return false;
      return Object.entries(entries).some(([key, note]) => typeof key === "string" && typeof note === "string");
    });
  })();
  const hasPersonal = (() => {
    if (!isRecord(ws.personal)) return false;
    return Object.entries(ws.personal).some(([, columns]) => {
      if (!isRecord(columns)) return false;
      return Object.entries(columns).some(([column, kind]) => typeof column === "string" && typeof kind === "string");
    });
  })();
  return !!(
    hasString(ws.goal) ||
    (Array.isArray(ws.decisions) && ws.decisions.some((item) => typeof item === "string")) ||
    hasString(ws.step) ||
    (Array.isArray(ws.done) && ws.done.some((item) => typeof item === "string")) ||
    hasString(ws.next) ||
    hasString(ws.progress) ||
    hasInspected ||
    hasPersonal
  );
}

export function WorkingNotes({ session }: { session: AssistantSession }) {
  const t = useT();
  const ws = session.working_state ?? {};
  const stats = session.stats ?? {};

  const statsEntries = Object.entries(stats).filter((entry): entry is [string, number] => {
    const [key, value] = entry;
    return (
      typeof value === "number" &&
      ["rounds", "validations", "probes", "previews", "query_checks"].includes(key)
    );
  });

  if (!hasContent(ws) && statsEntries.length === 0) {
    return (
      <section aria-label={t.assistant.notes} className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-ink">{t.assistant.notes}</h3>
        <p className="text-base text-ink-2">{t.assistant.notesEmpty}</p>
      </section>
    );
  }

  const decisions = renderStringArray(ws.decisions);
  const done = renderStringArray(ws.done);
  const inspectedSources = isRecord(ws.inspected)
    ? Object.entries(ws.inspected)
        .map(([source, entries]) => {
          if (!isRecord(entries)) return null;
          const stringEntries = Object.entries(entries).filter(
            (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string",
          );
          return stringEntries.length > 0 ? { source, entries: stringEntries } : null;
        })
        .filter((item): item is { source: string; entries: [string, string][] } => item !== null)
    : [];
  const personalSources = isRecord(ws.personal)
    ? Object.entries(ws.personal)
        .map(([source, columns]) => {
          if (!isRecord(columns)) return null;
          const stringColumns = Object.entries(columns).filter(
            (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string",
          );
          return stringColumns.length > 0 ? { source, columns: stringColumns } : null;
        })
        .filter((item): item is { source: string; columns: [string, string][] } => item !== null)
    : [];

  return (
    <section aria-label={t.assistant.notes} className="flex min-w-0 flex-col gap-3 [overflow-wrap:anywhere]">
      <h3 className="text-base font-semibold text-ink">{t.assistant.notes}</h3>
      <dl className="flex flex-col gap-3">
        {typeof ws.goal === "string" && ws.goal.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesGoal}</dt>
            <dd className="text-base text-ink">{ws.goal}</dd>
          </div>
        ) : null}
        {typeof ws.step === "string" && ws.step.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesStep}</dt>
            <dd className="text-base text-ink">{ws.step}</dd>
          </div>
        ) : null}
        {typeof ws.next === "string" && ws.next.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesNext}</dt>
            <dd className="text-base text-ink">{ws.next}</dd>
          </div>
        ) : null}
        {typeof ws.progress === "string" && ws.progress.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesProgress}</dt>
            <dd className="whitespace-pre-wrap text-base text-ink">{ws.progress}</dd>
          </div>
        ) : null}
        {decisions ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesDecisions}</dt>
            <dd>
              <ul className="flex flex-col gap-0.5">
                {decisions.map((decision, index) => (
                  <li key={index} className="text-base text-ink">
                    {decision}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
        {done ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesDone}</dt>
            <dd>
              <ul className="flex flex-col gap-0.5">
                {done.map((item, index) => (
                  <li key={index} className="text-base text-ink">
                    {item}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
        {inspectedSources.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesSources}</dt>
            <dd>
              <ul className="flex flex-col gap-1">
                {inspectedSources.map(({ source, entries }) => (
                  <li key={source} className="flex flex-col gap-0.5">
                    <span className="text-base font-semibold text-ink">{source}</span>
                    <ul className="flex flex-col gap-0.5">
                      {entries.map(([key, note]) => (
                        <li key={key} className="text-base text-ink">
                          {key} — {note}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
        {personalSources.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesPersonal}</dt>
            <dd>
              <ul className="flex flex-col gap-0.5">
                {personalSources.map(({ source, columns }) => (
                  <li key={source} className="text-base text-ink">
                    {source}:{" "}
                    {columns
                      .map(([column, kind]) => `${column} (${t.assistant.personalKinds[kind] ?? kind})`)
                      .join(", ")}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
        {statsEntries.length > 0 ? (
          <div className="flex flex-col gap-1">
            <dt className="text-sm font-semibold text-ink-2">{t.assistant.notesActivity}</dt>
            <dd className="flex flex-wrap gap-x-3 gap-y-1">
              {statsEntries.map(([key, value]) => (
                <span key={key} className="text-base text-ink">
                  {t.assistant.stats[key]}: {formatValue(value, "integer")}
                </span>
              ))}
            </dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
