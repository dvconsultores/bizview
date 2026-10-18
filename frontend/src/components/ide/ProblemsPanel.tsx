import { AlertTriangle, XCircle } from "lucide-react";
import type { ProjectIssue, ProjectValidation } from "../../api/types";
import { useT } from "../../i18n";

/** Validation problems of the whole project; selecting one of this project opens it at its line. */
export function ProblemsPanel(props: {
  validation: ProjectValidation | null;
  slug: string;
  onOpen: (file: string, line: number | null) => void;
}) {
  const t = useT();
  const errors = props.validation?.errors ?? [];
  const warnings = props.validation?.warnings ?? [];

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
      <li key={key}>
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
        {errors.length > 0 && <span className="text-xs font-normal text-danger">{t.projects.problemsCount(errors.length)}</span>}
        {warnings.length > 0 && <span className="text-xs font-normal text-warning-deep">{t.projects.warningsCount(warnings.length)}</span>}
      </h2>
      <div className="min-h-0 flex-1 overflow-auto p-1">
        {errors.length + warnings.length === 0 ? (
          <p className="p-3 text-sm text-ink-muted">{t.projects.noProblems}</p>
        ) : (
          <ul className="space-y-0.5">
            {errors.map((e, i) => item(e, true, `e${i}`))}
            {warnings.map((w, i) => item(w, false, `w${i}`))}
          </ul>
        )}
      </div>
    </section>
  );
}
