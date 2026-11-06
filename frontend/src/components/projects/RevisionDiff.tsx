import { FileDiff, Package } from "lucide-react";
import type { ImportLimits, ProjectDiff } from "../../api/types";
import { useT } from "../../i18n";
import { describeTally, type Preflight } from "../../lib/importPreflight";

/**
 * What a re-import does, before it does it (feature 055).
 *
 * The counts are always complete; the paths sit behind a disclosure so a 400-file project cannot
 * turn the card into a wall of text on a phone (constitution I). The two allowances of 049 travel
 * with it, because "what changes" and "what it costs" are the same question to an author.
 */
export function RevisionDiff({
  diff,
  mode,
  preflight,
  limits,
  baseRevision,
}: {
  diff: ProjectDiff;
  /** `created` reads "everything is new"; `reimported` compares with the previous revision. */
  mode: "created" | "reimported";
  preflight?: Preflight | null;
  limits?: ImportLimits | null;
  baseRevision?: number | null;
}) {
  const t = useT();
  const { counts } = diff;
  const empty = !Object.values(counts).some((value) => value > 0);
  const groups: { key: "added" | "changed" | "removed"; tone: string }[] = [
    { key: "added", tone: "text-success-bright" },
    { key: "changed", tone: "text-warning-deep" },
    { key: "removed", tone: "text-danger-bright" },
  ];
  const hasList = groups.some(({ key }) => diff[key].length > 0)
    || diff.specs.added.length > 0 || diff.specs.removed.length > 0
    || diff.ids.added.length > 0 || diff.ids.removed.length > 0;

  return (
    <div className="space-y-2" data-testid="revision-diff">
      <p className="text-sm text-ink-2">
        {mode === "created"
          ? t.projects.diff.createdTitle(counts.added)
          : t.projects.diff.reimportTitle(counts.added, counts.changed, counts.removed,
                                          baseRevision ?? null)}
      </p>
      {empty ? <p className="text-sm text-ink-muted">{t.projects.diff.empty}</p> : null}
      <ul className="grid gap-1 text-sm sm:grid-cols-2">
        <li className="flex items-center gap-2">
          <FileDiff className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
          <span>{t.projects.diff.files}</span>
          <span className="ml-auto font-mono text-xs text-ink-muted">
            {t.projects.diff.fileCounts(counts.added, counts.changed, counts.removed)}
          </span>
        </li>
        {(counts.specs_added > 0 || counts.specs_removed > 0) ? (
          <li className="flex items-center gap-2">
            <Package className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
            <span>{t.projects.diff.specs}</span>
            <span className="ml-auto font-mono text-xs text-ink-muted">
              {t.projects.diff.specCounts(counts.specs_added, counts.specs_removed)}
            </span>
          </li>
        ) : null}
        {(counts.ids_added > 0 || counts.ids_removed > 0) ? (
          <li className="flex items-center gap-2">
            <Package className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
            <span>{t.projects.diff.ids}</span>
            <span className="ml-auto font-mono text-xs text-ink-muted">
              {t.projects.diff.idCounts(counts.ids_added, counts.ids_removed)}
            </span>
          </li>
        ) : null}
      </ul>
      {hasList ? (
        <details className="rounded-card border border-line bg-surface-2 p-2 text-sm">
          <summary className="cursor-pointer font-semibold text-ink-2">
            {t.projects.diff.details}
          </summary>
          <div className="mt-2 space-y-2">
            {groups.map(({ key, tone }) => (
              diff[key].length ? (
                <div key={key}>
                  <p className={`text-xs font-semibold uppercase tracking-wide ${tone}`}>
                    {t.projects[key]}
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {diff[key].map((path) => (
                      <li key={path} className="break-all font-mono text-xs text-ink-muted">
                        {path}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null
            ))}
            {diff.specs.added.length || diff.specs.removed.length ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">
                  {t.projects.diff.specs}
                </p>
                <ul className="mt-1 space-y-0.5 font-mono text-xs text-ink-muted">
                  {diff.specs.added.map((folder) => <li key={`+${folder}`}>+ {folder}</li>)}
                  {diff.specs.removed.map((folder) => <li key={`-${folder}`}>− {folder}</li>)}
                </ul>
              </div>
            ) : null}
            {diff.ids.added.length || diff.ids.removed.length ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">
                  {t.projects.diff.ids}
                </p>
                <ul className="mt-1 space-y-0.5 font-mono text-xs text-ink-muted">
                  {diff.ids.added.map((id) => <li key={`+${id}`}>+ {id}</li>)}
                  {diff.ids.removed.map((id) => <li key={`-${id}`}>− {id}</li>)}
                </ul>
              </div>
            ) : null}
            {diff.truncated ? (
              <p className="text-xs text-ink-muted">{t.projects.diff.truncated}</p>
            ) : null}
          </div>
        </details>
      ) : null}
      {preflight && limits ? (
        <p className="font-mono text-xs text-ink-muted">
          {t.projects.preflight.artifacts}: {describeTally(preflight.artifacts, limits.artifacts)}
          {" · "}
          {t.projects.preflight.assets}: {describeTally(preflight.assets, limits.assets)}
        </p>
      ) : null}
    </div>
  );
}
