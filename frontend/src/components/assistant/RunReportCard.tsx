import { Check, FileText, TriangleAlert, XCircle } from "lucide-react";
import type { RunReport } from "../../api/types";
import { useT } from "../../i18n";

/**
 * Feature 039: the run report of a `/speckit-all` plan — stages, decisions, verification and what
 * is left for the human. The file `specs/<spec>/run-report.md` is the durable copy; this is the
 * same data rendered next to the conversation.
 */
export function RunReportCard({
  report,
  onOpenFile,
}: {
  report: RunReport;
  onOpenFile?: (path: string) => void;
}) {
  const t = useT();
  const c = t.assistant.runReport;
  const result =
    report.result === "applied"
      ? c.applied
      : report.result === "ready"
        ? c.ready
        : c.stopped.replace("{reason}", report.stop_reason ?? "—");

  return (
    <section
      data-run-report=""
      className="flex flex-col gap-3 rounded-xl border border-line bg-surface px-3.5 py-3 text-sm"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
          <p className="truncate font-medium text-ink">{c.title.replace("{spec}", report.spec)}</p>
        </div>
        <span className="inline-flex items-center rounded-full border border-line bg-canvas px-2 py-0.5 text-xs text-ink-2">
          {result}
        </span>
      </header>

      <ol className="flex flex-col gap-1" data-run-report-stages="">
        {report.stages.map((stage) => (
          <li key={`${stage.stage}-${stage.run_id}`} className="flex items-center gap-2 text-xs">
            {stage.status === "completed" ? (
              <Check className="h-3.5 w-3.5 text-success-strong" aria-hidden />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-danger-strong" aria-hidden />
            )}
            <span className="text-ink-2">{stage.stage}</span>
            <span className="text-ink-muted">{stage.status}</span>
          </li>
        ))}
      </ol>

      {report.decisions.length ? (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            {c.decisions}
          </p>
          <ul className="flex flex-col gap-1 text-xs text-ink-2">
            {report.decisions.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.stories.length ? (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            {c.verification}
          </p>
          <ul className="flex flex-col gap-1 text-xs text-ink-2">
            {report.stories.map((story) => (
              <li key={story.story} className="flex items-center gap-2">
                {story.ok ? (
                  <Check className="h-3.5 w-3.5 text-success-strong" aria-hidden />
                ) : (
                  <TriangleAlert className="h-3.5 w-3.5 text-warning-strong" aria-hidden />
                )}
                {story.story}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.pending.length ? (
        <div className="flex flex-col gap-1" data-run-report-pending="">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{c.pending}</p>
          <ul className="flex flex-col gap-1 text-xs text-ink-2">
            {report.pending.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {onOpenFile ? (
        <button
          type="button"
          onClick={() => onOpenFile(report.path)}
          className="self-start text-xs font-medium text-accent hover:underline"
        >
          {c.openFile.replace("{path}", report.path)}
        </button>
      ) : null}
    </section>
  );
}
