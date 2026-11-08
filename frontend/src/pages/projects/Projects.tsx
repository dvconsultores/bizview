import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { ChevronRight, Download, FolderKanban, GitBranch, Image as ImageIcon, Package, Search, Upload, X } from "lucide-react";
import { ApiError } from "../../api/client";
import { importProjectZip, projectsApi } from "../../api/projects";
import type {
  ImportLimits,
  ProjectDiff,
  ProjectImportResult,
  ProjectStatus,
  ProjectSummary,
} from "../../api/types";
import { RevisionDiff } from "../../components/projects/RevisionDiff";
import { StarterPanel } from "../../components/projects/StarterPanel";
import { Alert } from "../../components/Alert";
import { BackLink } from "../../components/BackLink";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { describeTally, tallyIndex, type Preflight } from "../../lib/importPreflight";
import { fold } from "../../lib/search";
import { readZipIndex } from "../../lib/zipIndex";

const STATUS_TONE: Record<ProjectStatus, "gray" | "green" | "amber" | "red"> = {
  borrador: "gray", aplicado: "green", cambios: "amber", retirado: "red",
};

const inputClass = "min-h-tap w-full rounded-card border border-line bg-surface px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function Projects() {
  const t = useT();
  const navigate = useNavigate();
  // Feature 061: arriving from Administración leaves a way back to it; the sidebar entry does not.
  const location = useLocation();
  const fromAdmin = (location.state as { from?: string } | null)?.from === "/admin";
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [imported, setImported] = useState<ProjectImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [folderWritable, setFolderWritable] = useState(true);
  // 049: read the archive's index before uploading, so an over-limit zip is never sent.
  const [limits, setLimits] = useState<ImportLimits | null>(null);
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [preflightFailed, setPreflightFailed] = useState(false);
  const [pending, setPending] = useState<File | null>(null);
  // 055: what the server says the import would do, and the two choices it can ask about.
  const [copy, setCopy] = useState(false);
  const [preview, setPreview] = useState<{ diff: ProjectDiff; mode: "created" | "reimported" } | null>(null);
  const [needsConfirm, setNeedsConfirm] = useState(false);
  // 057: the starter pack, built by the server for the selections the dialog collects.
  const [starterOpen, setStarterOpen] = useState(false);

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

  // 049: the allowances, so the pre-flight has something to measure against.
  useEffect(() => {
    let cancelled = false;
    projectsApi.limits().then((r) => !cancelled && setLimits(r)).catch(() => undefined);
    return () => { cancelled = true; };
  }, [attempt]);

  /** Chosen, not yet sent: read the archive's table of contents and decide whether to send it. */
  const choose = async (file: File | undefined) => {
    if (!file) return;
    setImported(null);
    setError(null);
    setPending(file);
    setPreflight(null);
    setPreflightFailed(false);
    const entries = await readZipIndex(file);
    if (entries === null || limits === null) {
      setPreflightFailed(entries === null && limits !== null);
      return;         // no index, or no limits yet: upload and let the server answer
    }
    setPreflight(tallyIndex(entries, limits));
  };

  /** Dry run: the server answers the diff for this archive without writing anything (055). */
  const previewImport = async (file: File | undefined = pending ?? undefined) => {
    if (!file) return;
    setImporting(true);
    setError(null);
    setPreview(null);
    setNeedsConfirm(false);
    try {
      const result = await importProjectZip(file, { copy, dryRun: true });
      setPreview({ diff: result.diff, mode: result.mode });
      setNeedsConfirm(Boolean(result.needs_confirmation));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setImporting(false);
    }
  };

  const importZip = async (file: File | undefined = pending ?? undefined,
                           replaceDraft = false) => {
    if (!file) return;
    setImporting(true);
    setImported(null);
    setError(null);
    try {
      const result = await importProjectZip(file, { copy, replaceDraft });
      setImported(result);
      setAttempt((n) => n + 1);
      setPending(null);
      setPreflight(null);
      setPreview(null);
      setNeedsConfirm(false);
    } catch (err) {
      // 409 draft_changed carries the question in the error body when the answer was not accepted.
      if (err instanceof ApiError && err.code === "draft_changed") setNeedsConfirm(true);
      else setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const blocked = preflight?.over ?? null;

  // Feature 025: finding a project in the list — by name, identifier or description, ignoring case
  // and accents. The filtering is local: the page already holds every project of the installation.
  const term = fold(query);
  const shown = items === null || term === "" ? items : items.filter((p) =>
    fold(`${p.name} ${p.slug} ${p.description}`).includes(term));

  return (
    <div className="space-y-5">
      {fromAdmin ? <BackLink to="/admin" /> : null}
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
                   onChange={(e) => void choose(e.target.files?.[0])} />
            <Button icon={<Download className="h-5 w-5" aria-hidden />}
                    onClick={() => setStarterOpen(true)}>
              {t.projects.starter.open}
            </Button>
            <Button variant="secondary" loading={importing} icon={<Upload className="h-5 w-5" aria-hidden />}
                    disabled={!folderWritable || pending !== null} onClick={() => fileInput.current?.click()}>
              {importing ? t.projects.importing : t.projects.importProject}
            </Button>
          </div>
        </div>
        <p className="text-sm text-ink-muted">{t.projects.importHint}</p>
        {pending && (
          <div className="space-y-2 rounded-card border border-line bg-subtle/40 p-3" role="status">
            <h2 className="text-sm font-semibold text-ink-2">{t.projects.preflight.title}</h2>
            {preflightFailed ? (
              <p className="text-sm text-ink-muted">{t.projects.preflight.readFailed}</p>
            ) : preflight === null ? (
              <p className="text-sm text-ink-muted">{t.projects.preflight.reading}</p>
            ) : (
              <>
                <ul className="grid gap-1 text-sm text-ink-2 sm:grid-cols-2">
                  <li className="flex items-center gap-2">
                    <Package className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
                    <span>{t.projects.preflight.artifacts}</span>
                    <span className={`ml-auto font-mono text-xs ${
                      preflight.artifacts.over.length ? "text-danger" : "text-ink-muted"}`}>
                      {describeTally(preflight.artifacts, limits!.artifacts)}
                    </span>
                  </li>
                  <li className="flex items-center gap-2">
                    <ImageIcon className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
                    <span>{t.projects.preflight.assets}</span>
                    <span className={`ml-auto font-mono text-xs ${
                      preflight.assets.over.length ? "text-danger" : "text-ink-muted"}`}>
                      {describeTally(preflight.assets, limits!.assets)}
                    </span>
                  </li>
                </ul>
                {preflight.ignored.length > 0 && (
                  <p className="text-xs text-ink-muted">{t.projects.preflight.ignored(preflight.ignored.length)}</p>
                )}
                {blocked && (
                  <Alert tone="error">
                    {t.projects.preflight.over(blocked === "artifacts"
                      ? t.projects.preflight.artifacts : t.projects.preflight.assets,
                      (preflight[blocked].over[0]))}
                  </Alert>
                )}
              </>
            )}
            <label className="flex items-start gap-2 text-sm text-ink-2">
              <input type="checkbox" checked={copy} className="mt-1 h-4 w-4"
                     onChange={(e) => { setCopy(e.target.checked); setPreview(null);
                                        setNeedsConfirm(false); }} />
              <span>
                <span className="block font-medium text-ink">{t.projects.copy}</span>
                <span className="block text-xs text-ink-muted">{t.projects.copyHint}</span>
              </span>
            </label>
            {preview ? (
              <RevisionDiff diff={preview.diff} mode={preview.mode}
                            preflight={preflight} limits={limits}
                            baseRevision={preview.diff.base_revision} />
            ) : null}
            {needsConfirm ? (
              <Alert tone="warning">
                <p className="font-semibold">{t.projects.replaceDraftTitle}</p>
                <p>{t.projects.replaceDraftText(pending?.name ?? "")}</p>
              </Alert>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {preview === null ? (
                <Button loading={importing} disabled={!folderWritable || blocked !== null}
                        onClick={() => void previewImport()}>
                  {t.projects.importNow}
                </Button>
              ) : needsConfirm ? (
                <Button loading={importing} onClick={() => void importZip(undefined, true)}>
                  {t.projects.replaceDraft}
                </Button>
              ) : (
                <Button loading={importing} onClick={() => void importZip()}>
                  {t.projects.importNow}
                </Button>
              )}
              <Button variant="ghost" onClick={() => { setPending(null); setPreflight(null);
                                                      setPreflightFailed(false); setPreview(null);
                                                      setNeedsConfirm(false); }}>
                {t.common.cancel}
              </Button>
            </div>
          </div>
        )}
        <ImportLimitsPanel limits={limits} onSaved={(next) => {
          setLimits(next);
          setPreflight(null);
          setPreflightFailed(false);
        }} />
      </Card>

      <StarterPanel open={starterOpen} onClose={() => setStarterOpen(false)} />

      {imported && imported.project && (
        <Card className="space-y-3 p-4 sm:p-5">
          <h2 className="text-lg font-semibold text-ink">
            {imported.mode === "reimported" && imported.revision
              ? t.projects.reimportedTitle(imported.project.name, imported.revision.number)
              : t.projects.importedTitle(imported.project.name)}
          </h2>
          {imported.diff ? (
            <RevisionDiff diff={imported.diff} mode={imported.mode}
                          baseRevision={imported.diff.base_revision} />
          ) : null}
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
          <Button onClick={() => navigate(`/proyectos/${imported.project!.slug}`)}>
            {t.projects.openProject}
          </Button>
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
          <p>{t.projects.emptyText}</p>
          {/* 057: the two downloads first — an author without a terminal starts here. */}
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            <Button icon={<Download className="h-5 w-5" aria-hidden />}
                    onClick={() => setStarterOpen(true)}>
              {t.projects.starter.download}
            </Button>
            <a href={projectsApi.starterTemplateUrl()} download
               className="inline-flex min-h-tap items-center justify-center gap-2 rounded-btn border border-line bg-surface px-4 text-base font-semibold text-ink-2 hover:bg-subtle">
              <Download className="h-5 w-5" aria-hidden />
              {t.projects.starter.downloadTemplate}
            </a>
          </div>
          <Button className="mt-3" variant="secondary" icon={<Upload className="h-5 w-5" aria-hidden />}
                  disabled={!folderWritable} onClick={() => fileInput.current?.click()}>
            {t.projects.importFirst}
          </Button>
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

/**
 * Feature 049: the two import allowances, editable by the super user.
 *
 * An empty field means "the deployment default" — the placeholder names it, and the server keeps
 * the value from the environment until someone writes a number here. Collapsed by default: this is
 * a setting an installation touches once, not something in the way of importing.
 */
function ImportLimitsPanel({ limits, onSaved }: {
  limits: ImportLimits | null;
  onSaved: (next: ImportLimits) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!limits) return;
    setDraft(Object.fromEntries(Object.entries(limits.stored)
      .map(([key, value]) => [key, value === null ? "" : String(value)])));
  }, [limits]);

  if (!limits) return null;

  const field = (kind: "artifacts" | "assets", column: "files" | "kb" | "mb") => {
    const key = `${kind === "artifacts" ? "artifact" : "asset"}_max_${column}`;
    const inherited = limits[kind][column === "files" ? "max_files" : `max_${column}` as
      "max_kb" | "max_mb"];
    return (
      <label className="space-y-1 text-sm font-semibold text-ink-2" key={key}>
        <span>{column === "files" ? t.projects.limits.files
          : column === "kb" ? t.projects.limits.kb : t.projects.limits.mb}</span>
        <input className={`${inputClass} font-mono`} inputMode="numeric" min={1} type="number"
               value={draft[key] ?? ""} placeholder={t.projects.limits.inherited(inherited)}
               aria-invalid={problems[key] ? true : undefined}
               onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
        {problems[key] && (
          <span className="block text-xs font-normal text-danger">
            {t.projects.limits.fieldProblem[problems[key]] ?? problems[key]}
          </span>
        )}
      </label>
    );
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setProblems({});
    setSaved(false);
    try {
      const body: Record<string, number | null> = {};
      for (const key of Object.keys(limits.stored)) {
        const raw = (draft[key] ?? "").trim();
        body[key] = raw === "" ? null : Number(raw);
      }
      onSaved(await projectsApi.saveLimits(body));
      setSaved(true);
    } catch (err) {
      const fields = err instanceof ApiError ? (err as ApiError & { fields?: Record<string, string> }).fields : null;
      if (fields) setProblems(fields);
      else setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border-t border-line pt-3">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              className="inline-flex min-h-tap items-center gap-2 text-sm font-semibold text-accent hover:underline">
        {open ? t.projects.limits.close : t.projects.limits.open}
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          <div>
            <h2 className="text-sm font-semibold text-ink-2">{t.projects.limits.title}</h2>
            <p className="text-xs text-ink-muted">{t.projects.limits.hint}</p>
          </div>
          <fieldset className="grid gap-3 sm:grid-cols-3">
            <legend className="mb-1 text-sm font-semibold text-ink-2">{t.projects.limits.artifacts}</legend>
            {field("artifacts", "files")}{field("artifacts", "kb")}{field("artifacts", "mb")}
          </fieldset>
          <fieldset className="grid gap-3 sm:grid-cols-3">
            <legend className="mb-1 text-sm font-semibold text-ink-2">{t.projects.limits.assets}</legend>
            {field("assets", "files")}{field("assets", "kb")}{field("assets", "mb")}
          </fieldset>
          <p className="text-xs text-ink-muted">{t.projects.limits.zipTotal(limits.zip_max_mb)}</p>
          {error && <Alert tone="error">{error}</Alert>}
          {saved && <Alert tone="success">{t.projects.limits.saved}</Alert>}
          <Button loading={saving} onClick={() => void save()}>{t.projects.limits.save}</Button>
        </div>
      )}
    </div>
  );
}
