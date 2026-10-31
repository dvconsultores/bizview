import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { ChevronRight, FolderKanban, FolderPlus, GitBranch, Search, Upload, X } from "lucide-react";
import { ApiError } from "../../api/client";
import { importProjectZip, projectsApi } from "../../api/projects";
import type { ProjectImportResult, ProjectStatus, ProjectSummary } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { fold } from "../../lib/search";

const STATUS_TONE: Record<ProjectStatus, "gray" | "green" | "amber" | "red"> = {
  borrador: "gray", aplicado: "green", cambios: "amber", retirado: "red",
};

const inputClass = "min-h-tap w-full rounded-card border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function Projects() {
  const t = useT();
  const navigate = useNavigate();
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [imported, setImported] = useState<ProjectImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [folderWritable, setFolderWritable] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    projectsApi.listing().then((r) => {
      if (cancelled) return;
      setItems(r.projects);
      setFolderWritable(r.folder_writable);
    })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : t.common.unexpected));
    return () => { cancelled = true; };
  }, [attempt, t]);

  // Suggested slug follows the name until the user edits it.
  useEffect(() => {
    if (!creating || slugTouched || !name.trim()) return;
    const id = window.setTimeout(() => {
      projectsApi.suggestSlug(name.trim()).then(setSlug).catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(id);
  }, [name, creating, slugTouched]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setFormError(null);
    try {
      const project = await projectsApi.create({ name: name.trim(), slug: slug || undefined });
      navigate(`/proyectos/${project.slug}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setBusy(false);
    }
  };

  const importZip = async (file: File | undefined) => {
    if (!file) return;
    setImporting(true);
    setImported(null);
    setError(null);
    try {
      setImported(await importProjectZip(file));
      setAttempt((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  // Feature 025: finding a project in the list — by name, identifier or description, ignoring case
  // and accents. The filtering is local: the page already holds every project of the installation.
  const term = fold(query);
  const shown = items === null || term === "" ? items : items.filter((p) =>
    fold(`${p.name} ${p.slug} ${p.description}`).includes(term));

  return (
    <div className="space-y-5">
      <PageHeader
        title={t.projects.title}
        subtitle={t.projects.subtitle}
        badge={items ? <Badge tone="accent">{t.projects.count(items.length)}</Badge> : null}
      />
      {!folderWritable && <Alert tone="warning">{t.projects.folderNotWritable}</Alert>}
      <Card className="space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          {items && items.length > 0 && (
            <div className="relative min-w-[13rem] flex-1">
              <label htmlFor="project-search" className="sr-only">{t.projects.search}</label>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" aria-hidden />
              <input
                id="project-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t.projects.searchPlaceholder}
                className="min-h-tap w-full rounded-card border border-line bg-surface pl-9 pr-10 text-sm text-ink placeholder:text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              />
              {query !== "" && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  aria-label={t.projects.clearSearch}
                  title={t.projects.clearSearch}
                  className="absolute right-1 top-1/2 inline-flex h-[28px] w-[28px] -translate-y-1/2 items-center justify-center rounded-lg text-ink-faint hover:bg-subtle hover:text-ink"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              )}
            </div>
          )}
          <div className="ml-auto flex flex-wrap justify-end gap-2">
            <input ref={fileInput} type="file" accept=".zip,application/zip" className="sr-only" id="project-zip"
                   aria-label={t.projects.chooseZip}
                   onChange={(e) => void importZip(e.target.files?.[0])} />
            <Button variant="secondary" loading={importing} icon={<Upload className="h-5 w-5" aria-hidden />}
                    disabled={!folderWritable} onClick={() => fileInput.current?.click()}>
              {importing ? t.projects.importing : t.projects.importProject}
            </Button>
            {!creating && (
              <Button icon={<FolderPlus className="h-5 w-5" aria-hidden />} disabled={!folderWritable}
                      onClick={() => setCreating(true)}>
                {t.projects.newProject}
              </Button>
            )}
          </div>
        </div>
        <p className="text-sm text-ink-muted">{t.projects.importHint}</p>
        {creating && (
          <form onSubmit={create} className="grid gap-3 sm:grid-cols-2" aria-label={t.projects.newProject}>
            <label className="space-y-1 text-sm font-semibold text-ink-2">
              <span>{t.projects.name}</span>
              <input className={inputClass} value={name} maxLength={80} autoFocus required
                     onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm font-semibold text-ink-2">
              <span>{t.projects.slug}</span>
              <input className={`${inputClass} font-mono`} value={slug} maxLength={50}
                     pattern="[a-z][a-z0-9\-]{1,49}" aria-describedby="slug-hint"
                     onChange={(e) => { setSlug(e.target.value); setSlugTouched(true); }} />
              <span id="slug-hint" className="block text-xs font-normal text-ink-muted">{t.projects.slugHint}</span>
            </label>
            {formError && <div className="sm:col-span-2"><Alert tone="error">{formError}</Alert></div>}
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button type="submit" loading={busy} disabled={!name.trim()}>{t.projects.create}</Button>
              <Button variant="ghost" onClick={() => { setCreating(false); setFormError(null); }}>
                {t.projects.cancel}
              </Button>
            </div>
          </form>
        )}
      </Card>

      {imported && (
        <Card className="space-y-3 p-4 sm:p-5">
          <h2 className="text-lg font-semibold text-ink">{t.projects.importedTitle(imported.project.name)}</h2>
          <div>
            <h3 className="text-sm font-semibold text-ink-2">{t.projects.ignoredFiles}</h3>
            {imported.ignored.length ? (
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-ink-muted">
                {imported.ignored.map((path) => <li key={path} className="break-all font-mono">{path}</li>)}
              </ul>
            ) : <p className="text-sm text-ink-muted">{t.projects.noIgnored}</p>}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-ink-2">{t.projects.problems}</h3>
            {imported.validation.errors.length ? (
              <ul className="mt-1 space-y-1 text-sm text-ink">
                {imported.validation.errors.map((p, i) => (
                  <li key={i}><span className="font-mono text-ink-muted">{p.file ?? ""}</span> {p.message}</li>
                ))}
              </ul>
            ) : <p className="text-sm text-ink-muted">{t.projects.noProblems}</p>}
          </div>
          <Button onClick={() => navigate(`/proyectos/${imported.project.slug}`)}>{t.projects.openProject}</Button>
        </Card>
      )}

      {error ? (
        <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.common.retry}</Button>}>
          {error}
        </Alert>
      ) : items === null ? (
        <div role="status" className="flex justify-center py-12 text-accent">
          <Spinner className="h-8 w-8" /><span className="sr-only">{t.common.loading}</span>
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon={<FolderKanban className="h-7 w-7" aria-hidden />} title={t.projects.empty}>
          {t.projects.emptyText}
        </EmptyState>
      ) : shown && shown.length === 0 ? (
        <div role="status" className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-4">
          <p className="min-w-0 flex-1 text-sm text-ink-muted">{t.projects.noMatch(query.trim())}</p>
          <Button variant="secondary" onClick={() => setQuery("")}>{t.projects.clearSearch}</Button>
        </div>
      ) : (
        <>
          {term !== "" ? (
            <p role="status" className="text-sm text-ink-muted">{t.projects.matches(shown?.length ?? 0)}</p>
          ) : null}
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {(shown ?? []).map((p) => (
            <li key={p.id}>
              <Link to={`/proyectos/${p.slug}`}
                    className="flex min-h-tap items-center rounded-card border border-line bg-surface p-4 hover:border-line-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                  {p.origin === "git" ? <GitBranch className="h-5 w-5" aria-hidden /> : <FolderKanban className="h-5 w-5" aria-hidden />}
                </span>
                <span className="ml-3 min-w-0 flex-1">
                  <span className="block truncate font-semibold text-ink">{p.name}</span>
                  <span className="block truncate font-mono text-xs text-ink-muted">{p.slug}</span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-ink-muted">
                    <Badge tone={STATUS_TONE[p.status]}>{t.projects.status[p.status]}</Badge>
                    <span>{t.projects.specsCount(p.spec_count)}</span>
                    <span>{t.projects.chatsCount(p.conversations)}</span>
                    {p.problems ? <Badge tone="red">{t.projects.problemsCount(p.problems)}</Badge> : null}
                    {p.last_activity_at && <span>{t.projects.lastActivity(formatDateTime(p.last_activity_at))}</span>}
                  </span>
                  {p.artifacts && (
                    <span className="mt-1 block text-xs text-ink-muted">
                      {t.projects.artifactsSummary(p.artifacts.integrations.length, p.artifacts.reports.length,
                                                   p.artifacts.distributions.length)}
                      {" · "}
                      {t.projects.appliedSummary(p.applied.integrations.length + p.applied.reports.length
                                                 + p.applied.distributions.length)}
                    </span>
                  )}
                </span>
                <ChevronRight className="ml-2 h-5 w-5 shrink-0 text-ink-faint" aria-hidden />
              </Link>
            </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
