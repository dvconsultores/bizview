import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useBranding } from "../../config/BrandingContext";
import { api, ApiError } from "../../api/client";
import type {
  AssistantSession,
  AssistantPreview,
  ReportDefinition,
  ReportData,
} from "../../api/types";
import { View } from "../../components/View";
import { Card } from "../../components/Card";
import { PageHeader } from "../../components/PageHeader";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Button } from "../../components/Button";
import { Badge } from "../../components/Badge";
import { Alert } from "../../components/Alert";
import { EmptyState } from "../../components/EmptyState";
import { CodeChip } from "../../components/CodeChip";
import { Spinner } from "../../components/Spinner";
import { ReportViews } from "../../components/report/ReportViews";
import { useOpenAssistant } from "../../components/assistant/useOpenAssistant";
import { ProblemList } from "../../components/assistant/ProblemList";
import { ReadinessChecklist, ReadinessPill } from "../../components/assistant/Readiness";
import { WorkingNotes } from "../../components/assistant/WorkingNotes";
import { RunStatus } from "../../components/assistant/RunStatus";
import { SessionIndicator } from "../../components/assistant/SessionIndicator";
import {
  AgentMapOverlay,
  useAgentMapToggle,
} from "../../components/assistant/AgentMap";
import { EditableTitle } from "../../components/assistant/EditableTitle";
import { isAssistantBusy, useAssistantBusy } from "../../components/assistant/useAssistantBusy";
import { SpecSelect } from "../../components/assistant/SpecSelect";
import { downloadPdf } from "../../lib/download";
import { t, useT } from "../../i18n";
import {
  Archive,
  MessagesSquare,
  Eye,
  CheckCircle2,
  XCircle,
  FileText,
  FileDown,
  Loader2,
  Network,
} from "lucide-react";

const DRAFT_GROUPS = [
  { key: "specIntegrations", prefix: "specs/integrations/", label: () => t.assistant.groupIntegrationSpec },
  { key: "integrations", prefix: "integrations/", label: () => t.assistant.groupIntegration },
  { key: "specReports", prefix: "specs/reports/", label: () => t.assistant.groupReportSpec },
  { key: "reports", prefix: "reports/", label: () => t.assistant.groupReport },
];

/** Draft files as the spec's cards (US1/AC2); each file in the first matching group. */
export function groupDraftFiles(files: Record<string, string>) {
  const names = Object.keys(files).sort();
  const groups = DRAFT_GROUPS.map((g) => ({
    key: g.key,
    label: g.label(),
    files: names.filter((n) => n.startsWith(g.prefix)),
  }));
  const other = names.filter((n) => !DRAFT_GROUPS.some((g) => n.startsWith(g.prefix)));
  return [...groups, { key: "other", label: t.assistant.groupOther, files: other }].filter(
    (g) => g.files.length > 0,
  );
}

export function AssistantSession() {
  const t = useT();
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<AssistantSession | null>(null);
  const map = useAgentMapToggle();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applySuccess, setApplySuccess] = useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const { ai_enabled } = useBranding();
  const openAssistant = useOpenAssistant();
  const [openFile, setOpenFile] = useState<{
    name: string;
    content: string;
  } | null>(null);
  const [previewReport, setPreviewReport] = useState<{
    reportId: string;
    definition: ReportDefinition | null;
    data: ReportData | null;
    error: string | null;
    loadingDef: boolean;
    loadingData: boolean;
  } | null>(null);
  const pollRef = useRef<number | null>(null);
  const { busy, markBusy, release } = useAssistantBusy(session, setSession);

  const clearPoll = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const loadSession = useCallback(async () => {
    if (!id) return;
    try {
      const s = await api.get<AssistantSession>(`/api/assistant/sessions/${id}`);
      setSession(s);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : t.assistant.failedToLoadSession
      );
    } finally {
      setLoading(false);
    }
  }, [id, t]);

  useEffect(() => {
    let cancelled = false;
    if (!id) return;
    api
      .get<AssistantSession>(`/api/assistant/sessions/${id}`)
      .then((s) => {
        if (!cancelled) setSession(s);
      })
      .catch((e) => {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : t.assistant.failedToLoadSession
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      clearPoll();
    };
  }, [id]);


  const archiveSession = async () => {
    if (!session || busy) return;
    setArchiving(true);
    setError(null);
    try {
      await api.post(`/api/assistant/sessions/${session.id}/archive`);
      setSession({ ...session, status: "archived" });
    } catch (e) {
      if (isAssistantBusy(e)) {
        markBusy();
        return;
      }
      setError(e instanceof ApiError ? e.message : t.assistant.failedToArchive);
    } finally {
      setArchiving(false);
    }
  };

  const startPreview = async () => {
    if (!session || busy) return;
    setPreviewing(true);
    setError(null);
    try {
      const { preview } = await api.post<{ preview: AssistantPreview }>(
        `/api/assistant/sessions/${session.id}/preview`
      );
      setSession({ ...session, preview });
      if (preview.status === "pending") {
        clearPoll();
        const start = Date.now();
        pollRef.current = window.setInterval(async () => {
          if (Date.now() - start > 300000) {
            clearPoll();
            return;
          }
          try {
            const { preview: p } = await api.get<{ preview: AssistantPreview }>(
              `/api/assistant/sessions/${session.id}/preview`
            );
            setSession((prev) => (prev ? { ...prev, preview: p } : prev));
            if (p.status !== "pending") {
              clearPoll();
              void loadSession();
            }
          } catch {
            clearPoll();
          }
        }, 3000);
      } else {
        await loadSession();   // the server added the outcome to the conversation
      }
    } catch (e) {
      if (isAssistantBusy(e)) {
        markBusy();
        return;
      }
      setError(e instanceof ApiError ? e.message : t.assistant.failedToPreview);
    } finally {
      setPreviewing(false);
    }
  };

  const applyDraft = async () => {
    if (!session || busy) return;
    setApplying(true);
    setError(null);
    setApplySuccess(null);
    try {
      const res = await api.post<{
        version: { id: number; reports: string[] };
        session: AssistantSession;
        revalidated: boolean;
      }>(`/api/assistant/sessions/${session.id}/apply`);
      setSession(res.session);
      setApplySuccess(
        t.assistant.appliedAsVersion.replace("{id}", String(res.version.id)) +
          (res.revalidated ? " " + t.assistant.revalidated : "")
      );
    } catch (e) {
      if (isAssistantBusy(e)) {
        markBusy();
        return;
      }
      if (
        e instanceof ApiError &&
        (e.code === "invalid_draft" ||
          e.code === "query_check_failed" ||
          e.code === "not_ready")
      ) {
        setError(e.message);
        await loadSession();
      } else {
        setError(e instanceof ApiError ? e.message : t.assistant.failedToApply);
      }
    } finally {
      setApplying(false);
    }
  };

  const downloadPreviewPdf = async (rid: string) => {
    if (!session || pdfBusy) return;
    setPdfBusy(rid);
    setPdfError(null);
    try {
      await downloadPdf(
        `/api/assistant/sessions/${session.id}/preview/report/${encodeURIComponent(rid)}/pdf`,
        `${rid}-vista-previa.pdf`,
        t.assistant.previewPdfError,
      );
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : t.assistant.previewPdfError);
    } finally {
      setPdfBusy(null);
    }
  };

  const loadPreviewReport = async (reportId: string) => {
    if (!session) return;
    setPreviewReport({
      reportId,
      definition: null,
      data: null,
      error: null,
      loadingDef: true,
      loadingData: false,
    });
    try {
      const def = await api.get<ReportDefinition>(
        `/api/assistant/sessions/${session.id}/preview/report/${reportId}`
      );
      setPreviewReport((prev) =>
        prev
          ? { ...prev, definition: def, loadingDef: false, loadingData: true }
          : prev
      );
      const data = await api.get<ReportData>(
        `/api/assistant/sessions/${session.id}/preview/report/${reportId}/data`
      );
      setPreviewReport((prev) =>
        prev ? { ...prev, data, loadingData: false, error: null } : prev
      );
    } catch (e) {
      setPreviewReport((prev) =>
        prev
          ? {
              ...prev,
              error:
                e instanceof ApiError
                  ? e.message
                  : t.assistant.failedToLoadPreview,
              loadingDef: false,
              loadingData: false,
            }
          : prev
      );
    }
  };

  const draftReportIds = () => {
    if (!session?.draft?.files) return [];
    const ids = new Set<string>();
    for (const path of Object.keys(session.draft.files)) {
      const m = path.match(/^reports\/([^/]+)\/report\.yaml$/);
      if (m) ids.add(m[1]);
    }
    return Array.from(ids);
  };

  const statusTone = (status: string) =>
    status === "open"
      ? "accent"
      : status === "applied"
        ? "success"
        : "neutral";

  const statusLabel = (status: string) =>
    status === "open"
      ? t.assistant.statusOpen
      : status === "applied"
        ? t.assistant.statusApplied
        : t.assistant.statusArchived;

  const changeSpec = async (spec: string) => {
    if (!session) return;
    try {
      setSession(
        await api.post<AssistantSession>(`/api/assistant/sessions/${session.id}/spec`, {
          spec,
        }),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.common.unexpected);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8" role="status">
        <Spinner />
      </div>
    );
  }

  if (!session) {
    return (
      <Alert tone="error">{error || t.assistant.failedToLoadSession}</Alert>
    );
  }

  const pendingPdfForReport = (rid: string) =>
    session.readiness?.pending?.some(
      (p) => p.code === "pdf" && p.file === `reports/${rid}/report.yaml`,
    ) ?? false;

  return (
    <div className="flex flex-col gap-4">
      <Breadcrumbs
        back="/"
        items={[
          { label: t.nav.admin, to: "/admin" },
          { label: t.assistant.draft },
          { label: session.title },
        ]}
      />
      <PageHeader
        title={
          <EditableTitle
            as="span"
            sessionId={session.id}
            title={session.title}
            onRenamed={(s) =>
              setSession((prev) => (prev ? { ...prev, title: s.title } : prev))
            }
            inputClassName="text-xl font-bold sm:text-2xl"
          >
            <span className="min-w-0 break-words">
              {t.assistant.draftTitle.replace("{title}", session.title)}
            </span>
          </EditableTitle>
        }
        badge={
          <>
            <Badge tone={statusTone(session.status)}>
              {statusLabel(session.status)}
            </Badge>
            {session.specs && session.specs.length > 0 ? (
              <SpecSelect
                current={session.current_spec ?? null}
                specs={session.specs}
                onChange={(spec) => void changeSpec(spec)}
              />
            ) : null}
            <SessionIndicator session={session} working={busy} onOpen={map.toggle} />
          </>
        }
        actions={
          <>
            {session.status !== "archived" && ai_enabled ? (
              <Button icon={<MessagesSquare className="h-4 w-4" />} onClick={() => openAssistant(session.id)}>
                {t.assistant.continueInChat}
              </Button>
            ) : null}
            {session.status === "open" ? (
              <Button
                variant="secondary"
                icon={<Archive className="h-4 w-4" />}
                loading={archiving}
                disabled={busy}
                onClick={archiveSession}
              >
                {t.assistant.archive}
              </Button>
            ) : null}
            <Button
              variant="secondary"
              icon={<Network className="h-4 w-4" />}
              onClick={(e) => map.toggle(e.currentTarget)}
              aria-pressed={map.open}
            >
              {t.assistant.agentMap.open}
            </Button>
          </>
        }
      />
      {map.open ? (
        <div className="relative -mt-4 h-0">
          <AgentMapOverlay
            placement="page"
            sessionId={session.id}
            title={session.title}
            busy={busy}
            onClose={() => map.close()}
          />
        </div>
      ) : null}
      {error && <Alert tone="error">{error}</Alert>}
      {applySuccess && <Alert tone="success">{applySuccess}</Alert>}
      <RunStatus session={session} busy={busy} onSession={setSession} release={release} />
      {session.applied_version_id != null && (
        <Alert tone="info">
          {t.assistant.producedVersion.replace("{id}", String(session.applied_version_id))}{" "}
          <Link to="/admin/espacio" className="font-semibold text-accent underline">
            {t.assistant.openWorkspace}
          </Link>
          {" · "}
          <a
            href={`/api/workspace/versions/${session.applied_version_id}/export.zip`}
            download
            className="font-semibold text-accent underline"
          >
            {t.assistant.downloadZip}
          </a>
        </Alert>
      )}
      {!ai_enabled && <Alert tone="info">{t.assistant.aiNotConfigured}</Alert>}
      {/* Draft review only: the conversation itself lives in the assistant panel. */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <div className="contents">
          <Card className="flex flex-col gap-3 p-3">
            <h3 className="text-sm font-semibold">{t.assistant.draft}</h3>
            {!session.draft ? (
              <EmptyState
                icon={<FileText className="h-5 w-5" />}
                title={t.assistant.noDraft}
              />
            ) : (
              <>
                <div className="flex flex-wrap items-start gap-2">
                  <Badge
                    tone={session.validation?.valid ? "success" : "danger"}
                    icon={
                      session.validation?.valid ? (
                        <CheckCircle2 className="h-3.5 w-3.5" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5" />
                      )
                    }
                  >
                    {session.validation?.valid
                      ? t.assistant.valid
                      : t.assistant.issues.replace(
                          "{n}",
                          String(session.validation?.errors?.length ?? 0)
                        )}
                  </Badge>
                  <ReadinessPill ready={!!session.readiness?.ready} />
                </div>
                {!session.validation?.valid &&
                  session.validation?.errors?.length ? (
                  <ProblemList problems={session.validation.errors} />
                ) : null}
                {session.validation?.warnings?.length ? (
                  <ProblemList problems={session.validation.warnings} tone="warning" />
                ) : null}
                {session.draft.summary && (
                  <p className="text-base text-ink-2">{session.draft.summary}</p>
                )}
                <div className="flex flex-col gap-1">
                  <h4 className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                    {t.assistant.files}
                  </h4>
                  {groupDraftFiles(session.draft.files).map((g) => (
                    <section
                      key={g.key}
                      aria-label={g.label}
                      className="flex flex-col gap-2 rounded-xl border border-line p-3"
                    >
                      <h4 className="text-sm font-semibold text-ink">{g.label}</h4>
                      {g.files.map((name) => (
                        <div key={name} className="min-w-0">
                          <button
                            onClick={() =>
                              setOpenFile({ name, content: session.draft!.files[name] })
                            }
                            className="min-h-tap max-w-full text-left"
                            aria-label={`${t.assistant.view} ${name}`}
                          >
                            <CodeChip>{name}</CodeChip>
                          </button>
                          <pre
                            aria-hidden="true"
                            className="mt-1 max-h-24 overflow-hidden whitespace-pre-wrap break-words font-mono text-xs text-ink-2"
                          >
                            {session.draft!.files[name].split("\n").slice(0, 6).join("\n")}
                          </pre>
                        </div>
                      ))}
                    </section>
                  ))}
                </div>
                <ReadinessChecklist session={session} />
                <div className="flex flex-col gap-2">
                  <Button
                    variant="secondary"
                    icon={<Eye className="h-4 w-4" />}
                    loading={previewing}
                    disabled={busy || !session.validation?.valid || session.status !== "open"}
                    onClick={startPreview}
                    block
                  >
                    {t.assistant.preview}
                  </Button>
                  <Button
                    variant="primary"
                    icon={<CheckCircle2 className="h-4 w-4" />}
                    loading={applying}
                    disabled={busy || !session.readiness?.ready || session.status !== "open"}
                    onClick={applyDraft}
                    block
                  >
                    {t.assistant.apply}
                  </Button>
                </div>
                {session.validation?.valid && !session.readiness?.ready ? (
                  <p className="text-sm text-ink-muted">{t.assistant.applyBlocked}</p>
                ) : null}
              </>
            )}
          </Card>
          {session.preview && (
            <Card className="flex flex-col gap-3 p-3">
              <h3 className="text-sm font-semibold">{t.assistant.preview}</h3>
              {session.preview.status === "pending" && (
                <div className="flex items-center gap-2 text-sm text-ink-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t.assistant.previewInProgress}
                </div>
              )}
              {session.preview.status === "succeeded" && (
                <>
                  <Badge
                    tone="success"
                    icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                  >
                    {t.assistant.previewReady}
                  </Badge>
                  {pdfError && <Alert tone="error">{pdfError}</Alert>}
                  {draftReportIds().map((rid) => (
                    <div key={rid} className="flex flex-col gap-1">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="ghost"
                          icon={<Eye className="h-4 w-4" />}
                          onClick={() => loadPreviewReport(rid)}
                          block
                        >
                          {t.assistant.view}: {rid}
                        </Button>
                        {!pendingPdfForReport(rid) ? (
                          <Button
                            variant="ghost"
                            icon={<FileDown className="h-4 w-4" />}
                            loading={pdfBusy === rid}
                            onClick={() => downloadPreviewPdf(rid)}
                          >
                            {t.assistant.previewPdf}: {rid}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  {session.preview.integrations &&
                    Object.entries(session.preview.integrations).map(
                      ([name, integ]) => (
                        <div key={name} className="flex flex-col gap-1">
                          <span className="text-sm font-medium">{name}</span>
                          {integ.status !== "succeeded" ? (
                            <Alert tone="error">{integ.message}</Alert>
                          ) : (
                            Object.entries(integ.datasets).map(
                              ([ds, info]) => (
                                <span key={ds} className="text-sm text-ink-2">
                                  {ds}: {info.rows}{" "}
                                  {info.rows === 1 ? "fila" : "filas"}
                                </span>
                              )
                            )
                          )}
                        </div>
                      )
                    )}
                </>
              )}
              {(session.preview.status === "failed" ||
                session.preview.status === "expired") && (
                <Alert tone="error">
                  {session.preview.message || t.assistant.previewFailed}
                </Alert>
              )}
            </Card>
          )}
        </div>
        <Card className="flex flex-col gap-3 p-3">
          <WorkingNotes session={session} />
        </Card>
      </div>

      <View
        open={!!openFile}
        title={openFile?.name || ""}
        onClose={() => setOpenFile(null)}
      >
        {openFile && (
          <pre className="whitespace-pre-wrap break-words font-mono text-sm">
            {openFile.content}
          </pre>
        )}
      </View>

      <View
        open={!!previewReport}
        title={
          previewReport
            ? t.assistant.previewTitle.replace(
                "{title}",
                previewReport.reportId
              )
            : ""
        }
        onClose={() => setPreviewReport(null)}
      >
        {previewReport && (
          <div className="flex flex-col gap-3">
            {previewReport.loadingDef && <Spinner />}
            {previewReport.error && (
              <Alert tone="error">{previewReport.error}</Alert>
            )}
            {previewReport.definition && previewReport.data && (
              <>
                <ReportViews
                  data={previewReport.data}
                  def={previewReport.definition}
                />
                <Alert tone="info">{t.assistant.previewNote}</Alert>
              </>
            )}
            {previewReport.loadingData && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}
          </div>
        )}
      </View>

    </div>
  );
}
