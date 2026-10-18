import { Link } from "react-router";
import { AlertTriangle, CheckCircle2, Download, FolderGit2, RotateCcw, ShieldCheck, Upload, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { WorkspaceReportDetail, WorkspaceSpec, WorkspaceSpecDocument, WorkspaceSpecFile, WorkspaceState, WorkspaceValidation, WorkspaceVersion } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Button, buttonClass } from "../../components/Button";
import { Card } from "../../components/Card";
import { CodeChip } from "../../components/CodeChip";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { View } from "../../components/View";
import { rich, t, useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";

const short = (s: string | null | undefined, n = 10) => (s ? s.slice(0, n) : "—");

const SPEC_FILES: WorkspaceSpecFile[] = ["spec.md", "plan.md", "tasks.md"];

function specTabLabel(file: WorkspaceSpecFile): string {
  switch (file) {
    case "spec.md": return t.workspace.specs.tabSpec;
    case "plan.md": return t.workspace.specs.tabPlan;
    case "tasks.md": return t.workspace.specs.tabTasks;
  }
}

function specTitle(spec: WorkspaceSpec): string {
  return spec.title ?? t.workspace.specs.untitled;
}

function statusTone(status: string | null): "green" | "blue" | "gray" {
  if (!status) return "gray";
  const s = status.toLowerCase();
  if (s.startsWith("implemented")) return "green";
  if (s.startsWith("approved")) return "blue";
  return "gray";
}

function shaShort(sha256: Record<string, string> | null): string {
  return sha256?.["spec.md"]?.slice(0, 12) ?? "—";
}

function specKind(kind: string): string {
  if (kind === "report") return t.workspace.specs.kindReport;
  if (kind === "integration") return t.workspace.specs.kindIntegration;
  return t.projects.kind[kind] ?? kind;
}

/** Spec archive grouped by owning project (feature 020); legacy keys belong to `principal`. */
function groupSpecs(v: WorkspaceVersion): { slug: string; name: string; specs: WorkspaceSpec[] }[] {
  const groups = new Map<string, WorkspaceSpec[]>();
  for (const spec of v.specs ?? []) {
    const slug = spec.project ?? "principal";
    groups.set(slug, [...(groups.get(slug) ?? []), spec]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
    .map(([slug, specs]) => ({ slug, name: v.projects?.[slug]?.name ?? slug, specs }));
}

function Version({ v, title }: { v: WorkspaceVersion; title: string }) {
  const t = useT();
  return (
    <Card className="space-y-3 p-5 sm:p-6">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <dl className="grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-2">
        <div><dt className="inline text-ink-muted">{t.workspace.manage.version}</dt><dd className="inline font-medium text-ink">#{v.id}</dd></div>
        <div><dt className="inline text-ink-muted">{t.workspace.manage.commit}</dt><dd className="inline"><CodeChip>{short(v.commit)}</CodeChip></dd></div>
        <div><dt className="inline text-ink-muted">{t.workspace.manage.appliedLabel}</dt><dd className="inline font-medium text-ink">{formatDateTime(v.applied_at)}</dd></div>
        <div><dt className="inline text-ink-muted">{t.workspace.manage.checksum}</dt><dd className="inline"><CodeChip>{short(v.checksum, 12)}</CodeChip></dd></div>
      </dl>
      <p className="text-sm text-ink-3 [overflow-wrap:anywhere]">
        <span className="text-ink-muted">{t.workspace.manage.integrations}</span> {v.integrations.join(", ") || "—"}
      </p>
      <p className="text-sm text-ink-3 [overflow-wrap:anywhere]">
        <span className="text-ink-muted">{t.workspace.manage.reports}</span> {v.reports.join(", ") || "—"}
      </p>
      {v.projects && Object.keys(v.projects).length > 0 && (
        <ul className="space-y-1 text-sm text-ink-3">
          {Object.entries(v.projects).map(([slug, p]) => (
            <li key={slug} className="[overflow-wrap:anywhere]">
              <Link to={`/proyectos/${slug}`} className="font-medium text-accent underline">{p.name}</Link>
              {": "}{[...p.integrations, ...p.reports, ...p.distributions].join(", ") || "—"}
            </li>
          ))}
        </ul>
      )}
      <a href={`/api/workspace/versions/${v.id}/export.zip`} download
        className={buttonClass("secondary", false, "gap-2")}>
        <Download className="h-5 w-5" aria-hidden />
        {t.assistant.downloadZip}
      </a>
    </Card>
  );
}

function Changes({ c }: { c: WorkspaceValidation["changes"] }) {
  const t = useT();
  const rows: [string, string[] | undefined][] = [[t.workspace.manage.changes.new, c.added], [t.workspace.manage.changes.modified, c.changed], [t.workspace.manage.changes.removed, c.removed]];
  const any = rows.some(([, v]) => v && v.length) || (c.dataset_changes?.length ?? 0) > 0;
  if (!any) return <p className="text-sm text-ink-muted">{t.workspace.manage.changes.none}</p>;
  return (
    <ul className="space-y-1 text-sm">
      {rows.filter(([, v]) => v && v.length).map(([label, v]) => (
        <li key={label} className="[overflow-wrap:anywhere]"><span className="font-medium">{label}:</span> {v!.join(", ")}</li>
      ))}
    </ul>
  );
}

function ReportDetails({ items }: { items: WorkspaceReportDetail[] }) {
  const t = useT();
  return (
    <Card className="space-y-4 p-5 sm:p-6">
      <h2 className="text-lg font-semibold text-ink">{t.workspace.reports.title}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-ink-2">{t.workspace.reports.empty}</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="rounded-xl border border-line p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="break-words text-sm font-medium text-ink">{item.id}</span>
                <Badge tone={item.mode === "direct" ? "blue" : "gray"}>
                  {item.mode === "direct" ? t.workspace.reports.modeDirect : t.workspace.reports.modeDataset}
                </Badge>
                {item.status === "broken" && (
                  <Badge tone="red" icon={<AlertTriangle className="h-3.5 w-3.5" aria-hidden />}>
                    {t.workspace.reports.broken}
                  </Badge>
                )}
                {item.status === "failing" && (
                  <Badge tone="amber">{t.workspace.reports.failing}</Badge>
                )}
              </div>
              <dl className="mt-2 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-ink-muted">{t.workspace.reports.source}</dt>
                  <dd className="mt-1 text-ink-2 [overflow-wrap:anywhere]">
                    {item.source || t.workspace.reports.noSource}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-muted">{t.workspace.reports.tables}</dt>
                  <dd className="mt-1 text-ink-2 [overflow-wrap:anywhere]">
                    {item.tables.length === 0 ? (
                      t.workspace.reports.noSource
                    ) : (
                      item.tables.map((table) => (
                        <CodeChip key={table} className="mr-1 break-all">
                          {table}
                        </CodeChip>
                      ))
                    )}
                  </dd>
                </div>
                {item.mode === "direct" && item.last_read_at ? (
                  <div>
                    <dt className="text-xs text-ink-muted">{t.workspace.reports.lastRead}</dt>
                    <dd className="mt-1 text-ink-2 [overflow-wrap:anywhere]">
                      {formatDateTime(item.last_read_at)}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function Workspace() {
  const t = useT();
  const toast = useToast();
  const [state, setState] = useState<WorkspaceState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<WorkspaceValidation | null>(null);
  const [busy, setBusy] = useState<"validate" | "apply" | "rollback" | null>(null);
  const [confirmRollback, setConfirmRollback] = useState(false);

  const [selected, setSelected] = useState<WorkspaceSpec | null>(null);
  const [specDoc, setSpecDoc] = useState<WorkspaceSpecDocument | null>(null);
  const [specLoading, setSpecLoading] = useState(false);
  const [specError, setSpecError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceSpecFile>("spec.md");
  const specRequestSeq = useRef(0);

  const load = useCallback(() => {
    setError(null);
    api.get<WorkspaceState>("/api/workspace").then(setState)
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected));
  }, [t]);
  useEffect(load, [load]);

  const validate = () => {
    setBusy("validate");
    setError(null);
    api.post<WorkspaceValidation>("/api/workspace/validate").then(setValidation)
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected))
      .finally(() => setBusy(null));
  };
  const apply = () => {
    setBusy("apply");
    setError(null);
    api.post<{ version: WorkspaceVersion }>("/api/workspace/apply")
      .then((r) => {
        toast(t.workspace.manage.applied(r.version.id));
        setValidation(null);
        load();
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected))
      .finally(() => setBusy(null));
  };
  const rollback = () => {
    setBusy("rollback");
    api.post<{ version: WorkspaceVersion }>("/api/workspace/rollback")
      .then((r) => {
        toast(t.workspace.manage.rolledBack(r.version.id));
        setConfirmRollback(false);
        load();
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected))
      .finally(() => setBusy(null));
  };

  const openSpec = (spec: WorkspaceSpec) => {
    const seq = ++specRequestSeq.current;
    setSelected(spec);
    setActiveTab("spec.md");
    setSpecDoc(null);
    setSpecError(null);
    setSpecLoading(true);
    api.get<WorkspaceSpecDocument>(`/api/workspace/specs?key=${encodeURIComponent(spec.key)}`)
      .then((doc) => {
        if (specRequestSeq.current === seq) setSpecDoc(doc);
      })
      .catch((e) => {
        if (specRequestSeq.current === seq) setSpecError(e instanceof ApiError ? e.message : t.common.unexpected);
      })
      .finally(() => {
        if (specRequestSeq.current === seq) setSpecLoading(false);
      });
  };

  const closeSpec = () => {
    specRequestSeq.current++;
    setSelected(null);
    setSpecDoc(null);
    setSpecError(null);
    setSpecLoading(false);
    setActiveTab("spec.md");
  };

  return (
    <div className="space-y-5">
      <Breadcrumbs back="/admin" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.workspace.manage.breadcrumb }]} />
      <PageHeader title={t.workspace.manage.title}
        subtitle={t.workspace.manage.subtitle} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {!state ? (
        error ? null : <div role="status" className="flex justify-center py-12 text-accent"><Spinner className="h-8 w-8" /><span className="sr-only">{t.common.loading}</span></div>
      ) : (
        <>
          <Card tone="accent" className="space-y-4 p-5 sm:p-6">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                <FolderGit2 className="h-5 w-5" aria-hidden />
              </span>
              <h2 className="text-lg font-semibold text-ink">{t.workspace.manage.mountedFolder}</h2>
            </div>
            {state.mounted ? (
              <dl className="space-y-2 text-sm">
                <div className="[overflow-wrap:anywhere]"><dt className="inline text-ink-muted">{t.workspace.manage.path}</dt><dd className="inline"><CodeChip className="break-all">{state.mounted.path}</CodeChip></dd></div>
                <div><dt className="inline text-ink-muted">{t.workspace.manage.commit}</dt><dd className="inline"><CodeChip>{short(state.mounted.commit)}</CodeChip></dd></div>
                <div><dt className="inline text-ink-muted">{t.workspace.manage.lock}</dt><dd className="inline"><CodeChip>{state.mounted.checksum ? short(state.mounted.checksum, 12) : t.workspace.manage.noLockFile}</CodeChip></dd></div>
              </dl>
            ) : (
              <p className="text-sm text-ink-muted">{rich(t.workspace.manage.notMounted, { init: <CodeChip>bizview init</CodeChip>, workspace: <CodeChip>workspace</CodeChip> })}</p>
            )}
            <div className="flex flex-wrap">
              <Button className="mb-2 mr-2" variant="secondary" loading={busy === "validate"} disabled={!state.mounted}
                icon={<ShieldCheck className="h-5 w-5" aria-hidden />} onClick={validate}>{t.workspace.manage.validate}</Button>
              <Button className="mb-2" loading={busy === "apply"} disabled={!validation?.ok}
                icon={<Upload className="h-5 w-5" aria-hidden />} onClick={apply}>{t.workspace.manage.apply}</Button>
            </div>
          </Card>

          {validation ? (
            <Card className="space-y-3 p-5 sm:p-6" aria-live="polite">
              <h2 className="flex items-center font-semibold text-ink">
                {validation.ok
                  ? <><CheckCircle2 className="mr-2 h-5 w-5 text-success-bright" aria-hidden />{t.workspace.manage.valid}</>
                  : <><XCircle className="mr-2 h-5 w-5 text-danger-bright" aria-hidden />{t.workspace.manage.errors(validation.errors.length)}</>}
              </h2>
              {validation.errors.length ? (
                <ul className="space-y-2 text-sm">
                  {validation.errors.map((e, i) => (
                    <li key={i} className="rounded-lg bg-danger-soft p-2 text-danger-deep [overflow-wrap:anywhere]">
                      <CodeChip className="mr-1">{e.code}</CodeChip> · <span className="font-medium">{e.entry}</span>: {e.message}
                    </li>
                  ))}
                </ul>
              ) : null}
              {validation.warnings.length ? (
                <ul className="space-y-2 text-sm">
                  {validation.warnings.map((w, i) => (
                    <li key={i} className="rounded-lg bg-warning-soft p-2 text-warning-deep [overflow-wrap:anywhere]">
                      <span className="font-medium">{w.entry}</span>: {w.message}
                    </li>
                  ))}
                </ul>
              ) : null}
              <div><Changes c={validation.changes} /></div>
            </Card>
          ) : null}

          {state.active ? <Version v={state.active} title={t.workspace.manage.activeVersion} /> : (
            <Alert tone="info">{t.workspace.manage.noActiveVersion}</Alert>
          )}

          {state.active ? (
            <Card className="space-y-4 p-5 sm:p-6">
              <h2 className="text-lg font-semibold text-ink">{t.workspace.specs.title}</h2>
              {!state.active.specs || state.active.specs.length === 0 ? (
                <p className="text-sm text-ink-2">{t.workspace.specs.empty}</p>
              ) : (
                <div className="space-y-5">
                  {groupSpecs(state.active).map((group) => (
                    <section key={group.slug} aria-label={group.name} className="space-y-2">
                      <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-2">
                        <Link to={`/proyectos/${group.slug}`} className="text-accent underline">{group.name}</Link>
                        <CodeChip className="text-xs">{group.slug}</CodeChip>
                      </h3>
                <ul className="space-y-3">
                  {group.specs.map((spec) => {
                    const titleText = specTitle(spec);
                    return (
                      <li key={spec.key} className="rounded-xl border border-line p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex min-w-0 flex-col gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone={spec.kind === "report" || spec.kind === "reporte" ? "blue" : "gray"}>
                                {specKind(spec.kind)}
                              </Badge>
                              <span className="break-words text-sm font-medium text-ink">{titleText}</span>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone={statusTone(spec.status)} wrap>
                                {spec.status ?? t.workspace.specs.noStatus}
                              </Badge>
                              {spec.folder ? <CodeChip className="text-xs">{spec.folder}</CodeChip> : null}
                            </div>
                          </div>
                          <Button
                            variant="secondary"
                            onClick={() => openSpec(spec)}
                            aria-label={t.workspace.specs.viewLabel(titleText)}
                          >
                            {t.workspace.specs.view}
                          </Button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                    </section>
                  ))}
                </div>
              )}
            </Card>
          ) : null}

          {state.active ? <ReportDetails items={state.report_details ?? []} /> : null}

          {state.previous ? (
            <div className="space-y-3">
              <Version v={state.previous} title={t.workspace.manage.previousVersion} />
              <Button variant="secondary" icon={<RotateCcw className="h-5 w-5" aria-hidden />}
                onClick={() => setConfirmRollback(true)}>{t.workspace.manage.rollbackPrevious}</Button>
            </div>
          ) : null}
          <p className="text-sm text-ink-muted">
            <Badge tone="blue">{t.workspace.manage.tipLabel}</Badge>{" "}
            {rich(t.workspace.manage.tipText, { cmd: <CodeChip>bizview validate --write-lock</CodeChip> })}
          </p>
        </>
      )}
      <View open={confirmRollback} title={t.workspace.manage.rollbackConfirmTitle} onClose={() => setConfirmRollback(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmRollback(false)}>{t.common.cancel}</Button>
          <Button loading={busy === "rollback"} onClick={rollback}>{t.workspace.manage.rollbackConfirmButton}</Button>
        </>}>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <p className="text-ink-3">{t.workspace.manage.rollbackDescription(state?.previous?.id ?? "")}</p>
      </View>

      <View open={selected !== null} title={selected ? specTitle(selected) : t.workspace.specs.untitled} onClose={closeSpec}>
        {selected ? (
          <div className="space-y-4">
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-muted">{t.workspace.specs.kindLabel}</dt>
                <dd className="mt-1">
                  {specKind(selected.kind)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">{t.workspace.specs.statusLabel}</dt>
                <dd className="mt-1">
                  <Badge tone={statusTone(selected.status)} wrap>
                    {selected.status ?? t.workspace.specs.noStatus}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">{t.workspace.specs.folderLabel}</dt>
                <dd className="mt-1">{selected.folder ? <CodeChip>{selected.folder}</CodeChip> : "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">{t.workspace.specs.fingerprint}</dt>
                <dd className="mt-1"><CodeChip>{shaShort(selected.sha256)}</CodeChip></dd>
              </div>
            </dl>

            {specLoading ? (
              <div role="status" className="flex justify-center py-12 text-accent">
                <Spinner className="h-8 w-8" />
                <span className="sr-only">{t.common.loading}</span>
              </div>
            ) : specError ? (
              <Alert tone="error">{specError}</Alert>
            ) : specDoc?.documents === null ? (
              <Alert tone="info">{t.workspace.specs.unavailable}</Alert>
            ) : specDoc?.documents ? (
              <div className="space-y-3">
                <div role="group" aria-label={t.workspace.specs.documentGroupLabel} className="flex flex-wrap gap-2">
                  {SPEC_FILES.map((file) => (
                    <button
                      key={file}
                      type="button"
                      aria-pressed={activeTab === file}
                      onClick={() => setActiveTab(file)}
                      className={`min-h-tap rounded-full px-4 text-sm font-medium ${
                        activeTab === file
                          ? "bg-primary text-on-primary shadow-sm"
                          : "bg-field text-ink-2 hover:bg-fill hover:text-ink"
                      }`}
                    >
                      {specTabLabel(file)}
                    </button>
                  ))}
                </div>
                <pre
                  role="region"
                  aria-label={specTabLabel(activeTab)}
                  className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] font-mono text-sm text-ink-2 rounded-xl bg-subtle p-4 ring-1 ring-inset ring-line"
                >
                  {specDoc.documents[activeTab]}
                </pre>
              </div>
            ) : null}
          </div>
        ) : null}
      </View>
    </div>
  );
}
