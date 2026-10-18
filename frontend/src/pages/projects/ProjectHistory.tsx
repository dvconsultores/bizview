import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { BackLink } from "../../components/BackLink";
import { RotateCcw } from "lucide-react";
import { ApiError } from "../../api/client";
import { isRevisionGroup, projectsApi } from "../../api/projects";
import type { HistoryItem, ProjectDetail, ProjectDiff, Revision, SpecTimeline } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { DiffView } from "../../components/ide/DiffView";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";

const selectClass = "min-h-tap w-full rounded-card border border-line bg-surface px-2 text-sm text-ink";

/** File history of a project: who changed what (people, the agent, Git, imports), line diffs,
 * restore, and the stage timeline of each spec (FR-011, FR-012). */
export function ProjectHistory() {
  const t = useT();
  const { slug = "" } = useParams<{ slug: string }>();
  const [search, setSearch] = useSearchParams();
  const file = search.get("file") ?? "";
  const spec = search.get("spec") ?? "";
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [paths, setPaths] = useState<string[]>([]);
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [picked, setPicked] = useState<Revision[]>([]);
  const [diff, setDiff] = useState<ProjectDiff | null>(null);
  const [restoring, setRestoring] = useState<Revision | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<SpecTimeline | null>(null);

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : t.common.unexpected);

  const load = useCallback(async (before?: number) => {
    setLoading(true);
    try {
      const page = await projectsApi.history(slug, { path: file || undefined, spec: spec || undefined, before });
      setItems((prev) => (before ? [...prev, ...page.items] : page.items));
      setNext(page.next_before);
    } catch (e) {
      fail(e);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, file, spec]);

  useEffect(() => {
    projectsApi.get(slug).then(setProject).catch(fail);
    projectsApi.tree(slug).then((tree) => setPaths(tree.files.map((f) => f.path))).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);
  useEffect(() => {
    setPicked([]);
    setDiff(null);
    void load();
  }, [load]);
  useEffect(() => {
    if (!spec) { setTimeline(null); return; }
    projectsApi.timeline(slug, spec).then(setTimeline).catch(() => setTimeline(null));
  }, [slug, spec]);

  const filter = (key: "file" | "spec", value: string) => {
    const params = new URLSearchParams(search);
    if (value) params.set(key, value); else params.delete(key);
    params.delete(key === "file" ? "spec" : "file");
    setSearch(params, { replace: true });
  };

  const pick = (rev: Revision) => {
    setDiff(null);
    setPicked((prev) => {
      if (prev.some((r) => r.id === rev.id)) return prev.filter((r) => r.id !== rev.id);
      const sameFile = prev.filter((r) => r.path === rev.path);
      return [...sameFile, rev].slice(-2);
    });
  };
  const compare = async () => {
    const [a, b] = [...picked].sort((x, y) => x.id - y.id);
    try {
      setDiff(await projectsApi.diff(slug, a.id, b?.id));
    } catch (e) {
      fail(e);
    }
  };
  const restore = async () => {
    if (!restoring) return;
    setBusy(true);
    try {
      const current = (await projectsApi.tree(slug)).files.find((f) => f.path === restoring.path);
      await projectsApi.restore(slug, restoring.id, current?.sha256 ?? null);
      setDone(t.projects.restored);
      setRestoring(null);
      void load();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const actor = (kind: string, name: string | null) =>
    name ?? ({ agent: t.projects.agent, external: t.projects.external, system: t.projects.system,
               git: t.projects.gitActor } as Record<string, string>)[kind] ?? kind;
  const command = (value: string) => t.projects.command[value.replace(/^\//, "")] ?? value;

  return (
    <div className="space-y-5">
      <BackLink to={`/proyectos/${slug}`} />
      <PageHeader title={t.projects.historyTitle(project?.name ?? slug)} />
      <Card className="grid gap-3 p-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm font-semibold text-ink-2">
          <span>{t.projects.filterFile}</span>
          <select className={selectClass} value={file} onChange={(e) => filter("file", e.target.value)}>
            <option value="">{t.projects.all}</option>
            {paths.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-sm font-semibold text-ink-2">
          <span>{t.projects.filterSpec}</span>
          <select className={selectClass} value={spec} onChange={(e) => filter("spec", e.target.value)}>
            <option value="">{t.projects.all}</option>
            {project?.specs.map((s) => <option key={s.folder} value={s.folder}>{s.folder}</option>)}
          </select>
        </label>
      </Card>

      {error && <Alert tone="error">{error}</Alert>}
      {done && <Alert tone="success">{done}</Alert>}

      {timeline && (
        <Card className="space-y-2 p-4">
          <h2 className="text-lg font-semibold text-ink">{t.projects.timelineOf(timeline.folder)}</h2>
          <ol className="space-y-1 text-sm">
            {timeline.stages.map((s, i) => (
              <li key={i} className="flex flex-wrap gap-2">
                <Badge tone={s.stage === "aplicada" ? "green" : "gray"}>{t.projects.stage[s.stage]}</Badge>
                <span className="text-ink-muted">{formatDateTime(s.time)}</span>
                {s.version != null && <span className="text-ink-muted">{t.projects.version(s.version)}</span>}
              </li>
            ))}
          </ol>
          {timeline.conversations.length > 0 && (
            <div className="text-sm">
              <h3 className="font-semibold text-ink-2">{t.projects.conversationsOfSpec}</h3>
              <ul className="mt-1 flex flex-wrap gap-2">
                {timeline.conversations.map((c) => (
                  <li key={c.id}><Link className="text-accent underline" to={`/proyectos/${slug}?chat=${c.id}`}>{c.title}</Link></li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {picked.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-card border border-line-accent bg-accent-soft p-3 text-sm text-ink">
          <span className="min-w-0 flex-1 break-all">
            {t.projects.compareFrom}: #{Math.min(...picked.map((r) => r.id))} · {t.projects.compareTo}:{" "}
            {picked.length === 2 ? `#${Math.max(...picked.map((r) => r.id))}` : t.projects.current}
          </span>
          <Button onClick={() => void compare()}>{t.projects.compare}</Button>
          <Button variant="ghost" onClick={() => { setPicked([]); setDiff(null); }}>{t.projects.cancel}</Button>
        </div>
      )}
      {diff && (
        <Card className="overflow-hidden">
          <h2 className="border-b border-line bg-subtle px-3 py-2 text-sm font-semibold text-ink">{t.projects.diffTitle(diff.path)}</h2>
          <DiffView hunks={diff.hunks} truncated={diff.truncated} caption={t.projects.diffTitle(diff.path)} />
        </Card>
      )}
      {restoring && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-card border border-warning-line bg-warning-soft p-3 text-sm text-warning-deep">
          <span className="min-w-0 flex-1 break-all">{t.projects.restoreConfirm(restoring.path)}</span>
          <Button loading={busy} onClick={() => void restore()}>{t.projects.restore}</Button>
          <Button variant="ghost" onClick={() => setRestoring(null)}>{t.projects.cancel}</Button>
        </div>
      )}

      <ol className="space-y-3">
        {items.map((item, i) => isRevisionGroup(item) ? (
          <li key={item.group_id}>
            <Card className="p-4">
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-semibold text-ink">{actor(item.actor, item.actor_name)}</span>
                <Badge tone="gray">{command(item.command)}</Badge>
                <span className="text-ink-muted">{formatDateTime(item.time)}</span>
              </p>
              <ul className="mt-2 space-y-1">
                {item.files.map((rev) => (
                  <li key={rev.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <label className="flex min-h-tap min-w-0 flex-1 items-center gap-2">
                      <input type="checkbox" checked={picked.some((r) => r.id === rev.id)} onChange={() => pick(rev)} />
                      <span className="break-all font-mono text-ink-2">{rev.path}</span>
                      <span className="text-xs text-ink-muted">{t.projects.op[rev.op] ?? rev.op}</span>
                    </label>
                    {project?.origin !== "git" && (
                      <Button variant="ghost" icon={<RotateCcw className="h-4 w-4" aria-hidden />}
                              onClick={() => { setDone(null); setRestoring(rev); }}>
                        {t.projects.restore}
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          </li>
        ) : (
          <li key={`event-${i}`} className="flex flex-wrap items-center gap-2 rounded-card border border-line-accent bg-accent-soft px-4 py-2 text-sm text-ink">
            <strong>{t.projects.event[item.event] ?? item.event}</strong>
            {item.version != null && <span>{t.projects.version(item.version)}</span>}
            {item.actor_name && <span className="text-ink-muted">{item.actor_name}</span>}
            <span className="text-ink-muted">{formatDateTime(item.time)}</span>
          </li>
        ))}
      </ol>
      {loading ? (
        <div role="status" className="flex justify-center py-6 text-accent"><Spinner className="h-6 w-6" /><span className="sr-only">{t.common.loading}</span></div>
      ) : next != null && (
        <Button variant="secondary" onClick={() => void load(next)}>{t.projects.loadMore}</Button>
      )}
    </div>
  );
}
