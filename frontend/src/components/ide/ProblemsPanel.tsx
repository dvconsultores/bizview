import { AlertTriangle, RotateCw, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import type { ProjectIssue, ProjectValidation } from "../../api/types";
import { useT } from "../../i18n";

/** Problems the user put aside for this project (kept per browser; nothing is deleted). */
const DISMISSED_KEY = "bizview.problems.dismissed";

function signature(issue: ProjectIssue): string {
  return `${issue.file ?? ""}|${issue.line ?? ""}|${issue.message}`;
}

function readDismissed(slug: string): string[] {
  try {
    const all = JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? "{}") as Record<string, string[]>;
    return all[slug] ?? [];
  } catch {
    return [];
  }
}

function writeDismissed(slug: string, values: string[]): void {
  try {
    const all = JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? "{}") as Record<string, string[]>;
    all[slug] = values;
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable: dismissal lasts for this page only */
  }
}

/** Validation problems of the whole project; selecting one of this project opens it at its line. */
export function ProblemsPanel(props: {
  validation: ProjectValidation | null;
  slug: string;
  onOpen: (file: string, line: number | null) => void;
  onRevalidate?: () => void;
  checking?: boolean;
}) {
  const t = useT();
  const errors = props.validation?.errors ?? [];
  const warnings = props.validation?.warnings ?? [];
  const [dismissed, setDismissed] = useState<string[]>([]);
  useEffect(() => setDismissed(readDismissed(props.slug)), [props.slug]);

  const hidden = new Set(dismissed);
  const shownErrors = errors.filter((issue) => !hidden.has(signature(issue)));
  const shownWarnings = warnings.filter((issue) => !hidden.has(signature(issue)));
  const dismissedHere = errors.length + warnings.length - shownErrors.length - shownWarnings.length;

  const dismiss = (issue: ProjectIssue) => {
    const next = [...new Set([...dismissed, signature(issue)])];
    setDismissed(next);
    writeDismissed(props.slug, next);
  };
  const restore = () => {
    setDismissed([]);
    writeDismissed(props.slug, []);
  };

  const item = (issue: ProjectIssue, error: boolean, key: string) => {
    const own = !!issue.file && (!issue.project || issue.project === props.slug);
    const body = (
      <span className="flex items-start gap-2">
        {error ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
               : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-deep" aria-hidden />}
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap gap-x-2 text-xs text-ink-muted">
            {issue.file && <span className="break-all font-mono">{issue.file}</span>}
            {issue.line != null && <span>{t.projects.line(issue.line)}</span>}
            {issue.project && issue.project !== props.slug && (
              <span>{t.projects.otherProject(issue.project)}</span>
            )}
          </span>
          <span className="mt-0.5 block text-sm text-ink">{issue.message}</span>
          {issue.fix && (
            <span className="mt-0.5 block text-sm text-ink-2">
              <strong>{t.projects.fix}</strong> {issue.fix}
            </span>
          )}
        </span>
      </span>
    );
    return (
      <li key={key} className="group relative">
        <button
          type="button"
          onClick={() => dismiss(issue)}
          aria-label={t.projects.dismissProblem}
          title={t.projects.dismissProblem}
          className="absolute right-1 top-1 z-10 rounded p-1 text-ink-muted hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
        {own ? (
          <button type="button" onClick={() => props.onOpen(issue.file as string, issue.line ?? null)}
                  className="min-h-tap w-full rounded-card px-3 py-2 text-left hover:bg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            {body}
          </button>
        ) : (
          <div className="px-3 py-2">{body}</div>
        )}
        {issue.expected != null && (
          <details className="px-9 pb-2">
            <summary className="cursor-pointer text-xs text-ink-muted">{t.projects.expected}</summary>
            <pre className="overflow-x-auto text-xs text-ink-2">{JSON.stringify(issue.expected, null, 2)}</pre>
          </details>
        )}
      </li>
    );
  };

  return (
    <section className="flex h-full min-h-0 flex-col" aria-labelledby="problems-heading">
      <h2 id="problems-heading" className="flex flex-wrap items-center gap-2 border-b border-line bg-subtle px-3 py-2 text-sm font-semibold text-ink">
        {t.projects.problemsPanel}
        {shownErrors.length > 0 && <span className="text-xs font-normal text-danger">{t.projects.problemsCount(shownErrors.length)}</span>}
        {shownWarnings.length > 0 && <span className="text-xs font-normal text-warning-deep">{t.projects.warningsCount(shownWarnings.length)}</span>}
        {props.onRevalidate && (
          <button
            type="button"
            onClick={props.onRevalidate}
            disabled={props.checking}
            aria-label={t.projects.recheck}
            title={t.projects.recheck}
            className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-normal text-ink-2 hover:bg-subtle hover:text-ink disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <RotateCw className={props.checking ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} aria-hidden />
            {t.projects.recheck}
          </button>
        )}
      </h2>
      <div className="min-h-0 flex-1 overflow-auto p-1">
        {shownErrors.length + shownWarnings.length === 0 ? (
          <p className="p-3 text-sm text-ink-muted">{t.projects.noProblems}</p>
        ) : (
          <ul className="space-y-0.5">
            {shownErrors.map((e, i) => item(e, true, `e${i}`))}
            {shownWarnings.map((w, i) => item(w, false, `w${i}`))}
          </ul>
        )}
        {dismissedHere > 0 && (
          <p className="flex items-center gap-2 px-3 py-2 text-xs text-ink-muted">
            {t.projects.dismissedCount(dismissedHere)}
            <button type="button" onClick={restore}
                    className="rounded px-1.5 py-0.5 underline hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
              {t.projects.showDismissed}
            </button>
          </p>
        )}
      </div>
    </section>
  );
}
