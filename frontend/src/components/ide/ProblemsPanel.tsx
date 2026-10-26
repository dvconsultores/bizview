import { AlertTriangle, ChevronDown, ChevronUp, RotateCw, Wand2, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import type { ProjectFix, ProjectIssue, ProjectValidation } from "../../api/types";
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
  collapsed?: boolean;
  onToggle?: () => void;
  /** 035: apply the validator's deterministic corrections, with or without an AI. */
  onApplyFix?: (fix: ProjectFix & { problem_id?: string | null }, all: ProjectIssue[]) => Promise<void>;
  applying?: boolean;
  lastDiff?: string | null;
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
  const fixable = [...shownErrors, ...shownWarnings].filter((issue) => issue.fix_data);

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
    // Outside the row's own button: a button inside a button is not valid markup.
    const fixButton = issue.fix_data && props.onApplyFix ? (
      <div className="px-9 pb-2">
        <button
          type="button"
          disabled={props.applying}
          onClick={() => void props.onApplyFix?.({ ...issue.fix_data!, problem_id: issue.problem_id }, [issue])}
          className="inline-flex min-h-tap items-center gap-1 rounded-lg border border-accent/40 bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-deep hover:bg-accent-soft/70 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          <Wand2 className="h-3.5 w-3.5" aria-hidden />
          {t.projects.applyFix}
        </button>
      </div>
    ) : null;
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
        {fixButton}
        {issue.expected != null && (
          <details className="px-9 pb-2">
            <summary className="cursor-pointer text-xs text-ink-muted">{t.projects.expected}</summary>
            <pre className="overflow-x-auto text-xs text-ink-2">{JSON.stringify(issue.expected, null, 2)}</pre>
          </details>
        )}
      </li>
    );
  };

  const collapsed = props.collapsed ?? false;
  return (
    <section className={collapsed ? "" : "flex h-full min-h-0 flex-col"}
             aria-labelledby="problems-heading">
      <h2 id="problems-heading" className="flex flex-wrap items-center gap-2 border-b border-line bg-subtle px-3 py-2 text-sm font-semibold text-ink">
        {t.projects.problemsPanel}
        {shownErrors.length > 0 && <span className="text-xs font-normal text-danger">{t.projects.problemsCount(shownErrors.length)}</span>}
        {shownWarnings.length > 0 && <span className="text-xs font-normal text-warning-deep">{t.projects.warningsCount(shownWarnings.length)}</span>}
        {props.onApplyFix && fixable.length > 1 ? (
          <button
            type="button"
            disabled={props.applying}
            onClick={() => void props.onApplyFix?.({ ...fixable[0].fix_data!,
                                                     problem_id: fixable[0].problem_id },
                                                   fixable)}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold text-accent-deep hover:bg-accent-soft disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <Wand2 className="h-3.5 w-3.5" aria-hidden />
            {t.projects.applyAllFixes(fixable.length)}
          </button>
        ) : null}
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
        {props.onToggle && (
          <button
            type="button"
            onClick={props.onToggle}
            aria-expanded={!collapsed}
            aria-controls="problems-body"
            aria-label={collapsed ? t.projects.showProblems : t.projects.hideProblems}
            title={collapsed ? t.projects.showProblems : t.projects.hideProblems}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-normal text-ink-2 hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {collapsed ? <ChevronUp className="h-3.5 w-3.5" aria-hidden />
                       : <ChevronDown className="h-3.5 w-3.5" aria-hidden />}
            <span className="sr-only">{collapsed ? t.projects.showProblems : t.projects.hideProblems}</span>
          </button>
        )}
      </h2>
      {!collapsed && (
        <div id="problems-body" className="min-h-0 flex-1 overflow-auto p-1">
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
      )}
    </section>
  );
}
