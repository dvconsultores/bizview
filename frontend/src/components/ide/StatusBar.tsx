import { CheckCircle2, XCircle } from "lucide-react";
import type { ProjectReadiness, ProjectLastApplied, ProjectStatus, ProjectValidation } from "../../api/types";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { Badge } from "../Badge";
import { Spinner } from "../Spinner";

export type SaveState = "idle" | "saving" | "saved" | "dirty";

const STATUS_TONE: Record<ProjectStatus, "gray" | "green" | "amber" | "red"> = {
  borrador: "gray", aplicado: "green", cambios: "amber", retirado: "red",
};

export function StatusBar(props: {
  validation: ProjectValidation | null;
  readiness: ProjectReadiness | null;
  status: ProjectStatus | null;
  /** The latest apply (version, time, who), not the first one (020 T086). */
  lastApplied: ProjectLastApplied | null;
  save: SaveState;
  busy?: boolean;
  /** Runs the action the pending reason asks for (today: the preview), so the bar is not just a
   * diagnosis: "Ejecuta la vista previa" becomes the button that runs it. */
  onRunPending?: () => void;
}) {
  const t = useT();
  const errors = props.validation?.errors.length ?? 0;
  const saveText = { saving: t.projects.saving, saved: t.projects.saved, dirty: t.projects.unsaved,
                     idle: null }[props.save];
  return (
    <div role="status" aria-live="polite"
         className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line bg-subtle px-3 py-1.5 text-xs text-ink-muted">
      {props.validation && (
        <span className="flex items-center gap-1">
          {props.validation.valid
            ? <CheckCircle2 className="h-3.5 w-3.5 text-success" aria-hidden />
            : <XCircle className="h-3.5 w-3.5 text-danger" aria-hidden />}
          {props.validation.valid ? t.projects.valid : t.projects.problemsCount(errors)}
        </span>
      )}
      {props.readiness && (
        // Why it is not ready, not just that it is not (owner, 2026-10-23: "idk how to apply"): the
        // backend already sends the reason ("Ejecuta la vista previa", "Comprueba este archivo con
        // check_query"), so it is shown here instead of leaving a greyed-out Apply unexplained.
        <span
          className="flex min-w-0 items-center gap-1"
          data-readiness-pending=""
          title={props.readiness.pending.map((item) => item.message).join("\n") || undefined}
        >
          {props.readiness.ready ? t.projects.ready : t.projects.notReady}
          {!props.readiness.ready && props.readiness.pending.length > 0 && (
            props.onRunPending && props.readiness.pending[0].code === "preview" ? (
              <button
                type="button"
                data-run-pending=""
                onClick={props.onRunPending}
                className="inline-flex max-w-[26rem] items-center gap-1 truncate rounded px-1 text-accent underline hover:text-accent-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1"
              >
                {t.projects.runPreviewNow}
              </button>
            ) : (
              <span className="max-w-[26rem] truncate text-ink-faint">
                · {props.readiness.pending[0].message}
              </span>
            )
          )}
        </span>
      )}
      {props.status && <Badge tone={STATUS_TONE[props.status]}>{t.projects.status[props.status]}</Badge>}
      <span>{props.lastApplied
        ? t.projects.lastAppliedBy(props.lastApplied.version, formatDateTime(props.lastApplied.at),
                                   props.lastApplied.by)
        : t.projects.neverApplied}</span>
      {saveText && <span>{saveText}</span>}
      {props.busy && (
        <span className="flex items-center gap-1 text-accent">
          <Spinner className="h-3 w-3" />
          {t.projects.agentWorking}
        </span>
      )}
    </div>
  );
}
