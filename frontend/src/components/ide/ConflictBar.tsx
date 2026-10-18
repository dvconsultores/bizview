import type { FileChangedCurrent } from "../../api/types";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { Button } from "../Button";

/** Someone else changed the file: a stale save (`stale`) or a change seen while editing (`disk`). */
export function ConflictBar(props: {
  kind: "stale" | "disk";
  current?: FileChangedCurrent | null;
  onDiff: () => void;
  onOverwrite?: () => void;
  onDiscard: () => void;
  onReload?: () => void;
}) {
  const t = useT();
  const when = props.current?.time ? formatDateTime(props.current.time) : "";
  return (
    <div role="alert" className="flex flex-wrap items-center gap-2 rounded-card border border-warning-line bg-warning-soft p-3 text-sm text-warning-deep">
      <span className="min-w-0 flex-1">
        <strong className="block">{t.projects.fileChanged}</strong>
        {props.kind === "stale" ? t.projects.fileChangedBy(props.current?.author ?? "?", when)
                                : t.projects.fileChangedOnDisk}
      </span>
      <Button variant="secondary" onClick={props.onDiff}>{t.projects.viewDiff}</Button>
      {props.kind === "stale" && props.onOverwrite && (
        <Button variant="danger" onClick={props.onOverwrite}>{t.projects.overwrite}</Button>
      )}
      {props.kind === "disk" && props.onReload && <Button onClick={props.onReload}>{t.projects.reload}</Button>}
      <Button variant="secondary" onClick={props.onDiscard}>{t.projects.discardMine}</Button>
    </div>
  );
}
