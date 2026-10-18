import { useEffect, useState, type FormEvent } from "react";
import { FolderPlus } from "lucide-react";
import { ApiError } from "../../api/client";
import { projectsApi } from "../../api/projects";
import type { AssistantSession, ProjectSummary } from "../../api/types";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { Button } from "../Button";

const field = "min-h-tap w-full rounded-card border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** Research R16: the first message of a new chat needs a project. The name and slug are
 * proposed from the message (no AI call) and editable; or an existing project is picked. */
export function ProjectProposal(props: {
  text: string;
  onCreated: (session: AssistantSession) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [existing, setExisting] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    projectsApi.proposal(props.text).then((p) => {
      if (!cancelled) { setName(p.name); setSlug(p.slug); }
    }).catch(() => undefined);
    projectsApi.list().then((list) => !cancelled && setProjects(list)).catch(() => undefined);
    return () => { cancelled = true; };
  }, [props.text]);

  const run = async (work: () => Promise<AssistantSession>) => {
    setBusy(true);
    setError(null);
    try {
      props.onCreated(await work());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    } finally {
      setBusy(false);
    }
  };
  const create = (e: FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const project = await projectsApi.create({ name: name.trim(), slug: slug.trim() || undefined });
      return projectsApi.createSession(project.slug);
    });
  };

  return (
    <section aria-labelledby="proposal-title" className="space-y-3 border-b border-line bg-canvas p-4">
      <h3 id="proposal-title" className="text-sm font-semibold text-ink">{t.projects.proposalTitle}</h3>
      <p className="text-sm text-ink-muted">{t.projects.proposalText}</p>
      <form onSubmit={create} className="grid gap-2 sm:grid-cols-2">
        <label className="space-y-1 text-xs font-semibold text-ink-2">
          <span>{t.projects.name}</span>
          <input className={field} value={name} maxLength={80} required onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="space-y-1 text-xs font-semibold text-ink-2">
          <span>{t.projects.slug}</span>
          <input className={`${field} font-mono`} value={slug} maxLength={50} onChange={(e) => setSlug(e.target.value)} />
        </label>
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <Button type="submit" loading={busy} disabled={!name.trim()} icon={<FolderPlus className="h-4 w-4" aria-hidden />}>
            {t.projects.create}
          </Button>
          <Button variant="ghost" onClick={props.onCancel}>{t.projects.cancel}</Button>
        </div>
      </form>
      {projects.length > 0 && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="min-w-0 flex-1 space-y-1 text-xs font-semibold text-ink-2">
            <span>{t.projects.useExisting}</span>
            <select className={field} value={existing} onChange={(e) => setExisting(e.target.value)}>
              <option value="">{t.projects.chooseProject}</option>
              {projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
            </select>
          </label>
          <Button variant="secondary" disabled={!existing || busy}
                  onClick={() => void run(() => projectsApi.createSession(existing))}>
            {t.projects.open}
          </Button>
        </div>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </section>
  );
}
