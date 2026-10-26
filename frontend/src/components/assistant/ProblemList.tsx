import { CodeChip } from "../CodeChip";
import type { AssistantIssue } from "../../api/types";
import { t, useT } from "../../i18n";

export function problemLocation(p: AssistantIssue): string {
  const base = p.file ?? p.entry;
  if (typeof p.path === "string") {
    const suffix = p.path === "" ? `#${t.assistant.problemRoot}` : `#${p.path}`;
    return `${base}${suffix}`;
  }
  return base;
}

export function ProblemList({
  problems,
  tone = "error",
  dense = false,
  onApplyFix,
  applying = false,
}: {
  problems: AssistantIssue[];
  tone?: "error" | "warning";
  dense?: boolean;
  /** 035: the validator already knows the correction; apply it without an AI. */
  onApplyFix?: (problem: AssistantIssue) => void;
  applying?: boolean;
}) {
  const t = useT();
  const gap = dense ? "gap-1" : "gap-2";
  if (problems.length === 0) return null;

  return (
    <ul aria-label={t.assistant.problems} className={`flex flex-col ${gap}`}>
      {problems.map((problem, index) => {
        const messageClass = tone === "error" ? "text-danger" : "text-warning-deep";
        const hasExpected =
          problem.expected && typeof problem.expected === "object" && Object.keys(problem.expected).length > 0;
        return (
          <li key={index} className={`flex flex-col ${dense ? "gap-0.5" : "gap-1"}`}>
            <div className="flex flex-wrap items-center gap-1">
              <CodeChip>{problemLocation(problem)}</CodeChip>
            </div>
            <p className={`text-sm ${messageClass}`}>{problem.message}</p>
            {problem.fix_data && onApplyFix ? (
              <button
                type="button"
                disabled={applying}
                onClick={() => onApplyFix(problem)}
                className="inline-flex min-h-tap w-fit items-center gap-1 rounded-lg border border-accent/40 bg-accent-soft px-2 py-1 text-xs font-semibold text-accent-deep hover:bg-accent-soft/70 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                {t.projects.applyFix}
              </button>
            ) : null}
            {problem.fix ? (
              <p className="text-sm text-ink-2">
                <strong>{t.assistant.problemFix}:</strong> {problem.fix}
              </p>
            ) : null}
            {hasExpected ? (
              <details className="text-sm">
                <summary className="min-h-tap cursor-pointer text-ink-2">{t.assistant.problemExpected}</summary>
                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-sm text-ink-2">
                  {JSON.stringify(problem.expected, null, 2)}
                </pre>
              </details>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
