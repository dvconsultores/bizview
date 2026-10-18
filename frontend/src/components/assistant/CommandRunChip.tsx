import { AlertTriangle, Check, Clock, FileText, Loader2, RotateCcw, Square, XCircle } from "lucide-react";
import type { CommandRun, CommandRunStatus } from "../../api/types";
import { useT } from "../../i18n";

const MAX_FILES = 5;

const PILL: Record<CommandRunStatus, string> = {
  running: "bg-accent-soft text-accent",
  waiting: "bg-accent-soft text-accent",
  completed: "bg-success-soft text-success-strong",
  interrupted: "bg-warning-soft text-warning-strong",
  failed: "bg-danger-soft text-danger-strong",
};

const ICON: Record<CommandRunStatus, typeof Check> = {
  running: Loader2,
  waiting: Clock,
  completed: Check,
  interrupted: AlertTriangle,
  failed: XCircle,
};

/** One command run in the transcript (feature 021 plan §6): status, files, Terminar/re-run. */
export function CommandRunChip(props: {
  run: CommandRun;
  onFinish?: () => void;
  finishing?: boolean;
  onRerun?: (text: string) => void;
  onOpenFile?: (path: string) => void;
}) {
  const t = useT();
  const c = t.assistant.commands;
  const { run, onFinish, finishing, onRerun, onOpenFile } = props;
  const active = run.status === "running" || run.status === "waiting";
  const title = (
    run.spec ? (active ? c.chipRunning : c.chipDone) : active ? c.chipRunningNoSpec : c.chipDoneNoSpec
  )
    .replace("{command}", run.command)
    .replace("{spec}", run.spec ?? "");
  const paths = [...new Set(run.files.map((f) => f.path))];
  const shown = paths.slice(0, MAX_FILES);
  const Icon = ICON[run.status];

  return (
    <div data-command-run={run.id} className="rounded-xl border border-line bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
        <span className="min-w-0 font-medium text-ink">{title}</span>
        <span
          data-status={run.status}
          className={`ml-auto rounded-full px-2 py-0.5 text-xs ${PILL[run.status]}`}
        >
          {c.status[run.status]}
        </span>
      </div>
      {shown.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {shown.map((path) =>
            onOpenFile ? (
              <button
                key={path}
                type="button"
                onClick={() => onOpenFile(path)}
                aria-label={c.openFile.replace("{path}", path)}
                className="inline-flex min-h-tap items-center gap-1 rounded-md border border-line px-2 font-mono text-xs text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                <FileText className="h-3 w-3" aria-hidden />
                {path}
              </button>
            ) : (
              <span key={path} className="inline-flex items-center gap-1 font-mono text-xs text-ink-2">
                <FileText className="h-3 w-3" aria-hidden />
                {path}
              </span>
            ),
          )}
          {paths.length > MAX_FILES ? (
            <span className="text-xs text-ink-muted">{c.moreFiles(paths.length - MAX_FILES)}</span>
          ) : null}
        </div>
      ) : null}
      {run.status === "waiting" && onFinish ? (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={onFinish}
            disabled={finishing}
            className="inline-flex min-h-tap items-center gap-2 rounded-lg border border-line px-3 text-sm text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
          >
            <Square className="h-4 w-4" aria-hidden />
            {c.finish}
          </button>
        </div>
      ) : null}
      {run.status === "interrupted" && onRerun ? (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => onRerun(`/${run.command} `)}
            className="inline-flex min-h-tap items-center gap-2 rounded-lg border border-line px-3 text-sm text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <RotateCcw className="h-4 w-4" aria-hidden />
            {c.rerun}
          </button>
        </div>
      ) : null}
    </div>
  );
}
