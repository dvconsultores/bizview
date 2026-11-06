import { Download, History, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { projectsApi } from "../../api/projects";
import { ApiError } from "../../api/client";
import type { ProjectRevision, ProjectRevisionList } from "../../api/types";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { Button } from "../Button";
import { Spinner } from "../Spinner";
import { useToast } from "../Toast";

const TONE: Record<string, "gray" | "green" | "amber" | "blue"> = {
  draft: "amber", applied: "green", previous: "blue", replaced: "gray",
};

/**
 * A project's own revisions (feature 055): every import, every editor save and every revert, newest
 * first, with its diff and a download each.
 *
 * Reverting is the one action here that writes and applies, so it asks first — inline, never in a
 * modal (the product's rule, and 037's own "no `role=dialog`" gate).
 */
export function RevisionList({
  slug,
  onReverted,
}: {
  slug: string;
  onReverted?: () => void;
}) {
  const t = useT();
  const toast = useToast();
  const [data, setData] = useState<ProjectRevisionList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await projectsApi.revisions(slug));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    }
  }, [slug, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const revert = async (row: ProjectRevision) => {
    setBusy(row.number);
    setError(null);
    try {
      const result = await projectsApi.revert(slug, row.number);
      if (result.missing?.length) {
        toast(t.projects.revision.missing(result.missing.length), "warning");
      } else {
        toast(t.projects.revision.reverted(row.number));
      }
      setAsking(null);
      await load();
      onReverted?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setBusy(null);
    }
  };

  if (error && !data) return <Alert tone="error">{error}</Alert>;
  if (!data) {
    return (
      <div role="status" className="flex justify-center py-6 text-accent">
        <Spinner className="h-6 w-6" /><span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-muted">{t.projects.revision.hint(data.keep)}</p>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {data.items.length === 0 ? (
        <p className="text-sm text-ink-muted">{t.projects.revision.empty}</p>
      ) : (
        <ol className="divide-y divide-line-soft">
          {data.items.map((row) => {
            const isDraft = row.status === "draft";
            return (
              <li key={row.number} className="py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={TONE[row.status] ?? "gray"} icon={<History className="h-3.5 w-3.5" aria-hidden />}>
                    {t.projects.revision.number(row.number)}
                  </Badge>
                  <span className="text-sm font-semibold text-ink">
                    {t.projects.revision.status[row.status]}
                  </span>
                  <span className="text-sm text-ink-muted">
                    {t.projects.revision.source[row.source]}
                  </span>
                  <span className="text-xs text-ink-muted">
                    {t.projects.revision.files(row.files)}
                  </span>
                  <span className="ml-auto flex items-center gap-1">
                    <a href={projectsApi.revisionZipUrl(slug, row.number)} download
                       aria-label={t.projects.revision.download(row.number)}
                       title={t.projects.revision.download(row.number)}
                       className="control-compact inline-flex min-w-tap items-center justify-center rounded-lg text-ink-2 hover:bg-subtle hover:text-ink">
                      <Download className="h-4 w-4" aria-hidden />
                    </a>
                    {isDraft ? null : (
                      <Button size="sm" variant="ghost"
                              icon={<RotateCcw className="h-4 w-4" aria-hidden />}
                              loading={busy === row.number}
                              onClick={() => setAsking(row.number)}>
                        {t.projects.revision.revert}
                      </Button>
                    )}
                  </span>
                </div>
                <p className="mt-1 text-xs text-ink-muted">
                  {t.projects.revision.by(row.by ?? t.projects.revision.source[row.source],
                                           formatDateTime(row.created_at))}
                  {" · "}
                  {t.projects.diff.fileCounts(row.diff.counts.added, row.diff.counts.changed,
                                              row.diff.counts.removed)}
                </p>
                {asking === row.number ? (
                  <div className="mt-2 rounded-card border border-warning-line bg-warning-soft p-3 text-sm text-warning-deep">
                    <p>{t.projects.revision.revertConfirm(row.number)}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button size="sm" loading={busy === row.number} onClick={() => void revert(row)}>
                        {t.projects.confirm}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setAsking(null)}>
                        {t.common.cancel}
                      </Button>
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
