import {
  Maximize2,
  Minimize2,
  MoreHorizontal,
  Network,
  Plus,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError } from "../../api/client";
import { projectsApi } from "../../api/projects";
import type { AssistantSession, ProjectFix } from "../../api/types";
import { useBranding } from "../../config/BrandingContext";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { useShellChrome } from "../ShellChrome";
import { AgentMapOverlay, useAgentMapToggle } from "./AgentMap";
import { AssistantChat } from "./AssistantChat";
import { AssistantHistory } from "./AssistantHistory";
import { PanelResizer } from "./PanelResizer";
import { EditableTitle } from "./EditableTitle";
import { useAssistantPanel } from "./AssistantPanelContext";
import { ProblemList } from "./ProblemList";
import { ProjectProposal } from "./ProjectProposal";
import { ReadinessPill } from "./Readiness";
import { SessionIndicator } from "./SessionIndicator";
import { SpecSelect } from "./SpecSelect";

const ICON_BUTTON =
  "inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl text-ink-muted hover:bg-subtle hover:text-ink";

/** The one assistant chat (feature 014): docked at the right from 1024 px (Customer A style,
 * expandable), or as the Asistente page on phones. Header: conversations, new, expand, close.
 * A side panel, not a modal: no backdrop, the page stays usable; Esc inside it closes it. */
export function AssistantView({ placement }: { placement: "docked" | "page" }) {
  const t = useT();
  const navigate = useNavigate();
  const { ai_enabled } = useBranding();
  const { mode, sessionId, width, setWidth, close, setExpanded, setSessionId } =
    useAssistantPanel();
  const { hidden: chromeHidden } = useShellChrome();
  const [session, setSession] = useState<AssistantSession | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [chatKey, setChatKey] = useState(0);
  const [chatActive, setChatActive] = useState(false);
  // 035: applying a deterministic fix from the conversation's problem list.
  const [fixing, setFixing] = useState(false);
  // 036: the conversation's stored tool results can lose their call; repairing pairs them again.
  const [menuOpen, setMenuOpen] = useState(false);
  const [repairing, setRepairing] = useState(false);
  const [repairNotice, setRepairNotice] = useState<string | null>(null);
  // Feature 020: the first message of a new chat waits for its project (inline proposal).
  const [proposal, setProposal] = useState<{
    text: string;
    resolve: (s: AssistantSession) => void;
    reject: (e: unknown) => void;
  } | null>(null);
  const map = useAgentMapToggle();
  const mapOpenRef = useRef(false);
  const asideRef = useRef<HTMLElement | null>(null);
  const loadedId = useRef<number | null>(null);
  const docked = placement === "docked";

  /** Apply the validator's fix from the conversation's list; reload the session to show the result. */
  const applyProblemFix = async (problem: { fix_data?: ProjectFix | null;
                                            problem_id?: string | null }) => {
    const slug = session?.project?.slug;
    if (!slug || fixing || !problem.fix_data) return;
    setFixing(true);
    try {
      await projectsApi.applyFixes(slug, [{ ...problem.fix_data, problem_id: problem.problem_id }]);
      const fresh = await api.get<AssistantSession>(`/api/assistant/sessions/${session!.id}`);
      setSession(fresh);
    } catch (e) {
      setLoadError(true);
      console.error(e);
    } finally {
      setFixing(false);
    }
  };

  /** 036: repair from the header menu — same call the error bubble offers. */
  const repairConversation = async () => {
    if (!session || repairing) return;
    setMenuOpen(false);
    setRepairing(true);
    setRepairNotice(null);
    try {
      const report = await api.post<{ paired: number; orphans: number }>(
        `/api/assistant/sessions/${session.id}/repair`, {});
      setSession(await api.get<AssistantSession>(`/api/assistant/sessions/${session.id}`));
      setRepairNotice(
        report.paired || report.orphans
          ? t.ai.repairDone(report.paired, report.orphans)
          : t.ai.repairNothing,
      );
    } catch (e) {
      setRepairNotice(
        e instanceof ApiError ? t.ai.repairFailed(e.message) : t.common.unexpected,
      );
    } finally {
      setRepairing(false);
    }
  };

  useEffect(() => {
    mapOpenRef.current = map.open;
  }, [map.open]);

  // Load the remembered/selected conversation once per id (not again for one just created).
  useEffect(() => {
    if (!ai_enabled || sessionId === null || loadedId.current === sessionId)
      return;
    let cancelled = false;
    let settled = false;
    loadedId.current = sessionId;
    api
      .get<AssistantSession>(`/api/assistant/sessions/${sessionId}`)
      .then((s) => {
        settled = true;
        if (!cancelled) {
          setSession(s);
          setLoadError(false);
        }
      })
      .catch((e) => {
        settled = true;
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          loadedId.current = null;
          setSessionId(null);
        } else {
          loadedId.current = null; // a later open or selection tries again
          setLoadError(true);
        }
      });
    return () => {
      cancelled = true;
      // Cancelled before it finished (StrictMode runs effects twice in development, or the
      // panel closed): release the guard so the next run loads it again.
      if (!settled && loadedId.current === sessionId) loadedId.current = null;
    };
  }, [ai_enabled, sessionId, setSessionId]);

  useEffect(() => {
    if (!docked) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && asideRef.current?.contains(e.target as Node)) {
        if (mapOpenRef.current) {
          return;
        }
        close();
        document.getElementById("assistant-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [docked, close]);

  if (!ai_enabled) {
    return docked ? null : (
      <p className="rounded-2xl border border-line bg-surface p-6 text-center text-sm text-ink-2">
        {t.assistant.aiNotConfigured}
      </p>
    );
  }

  const onSession = (s: AssistantSession) => {
    loadedId.current = s.id;
    setSession(s);
    setSessionId(s.id);
  };
  const newConversation = () => {
    loadedId.current = null;
    setSession(null);
    setSessionId(null);
    setLoadError(false);
    setChatActive(false);
    map.close(false);
    setChatKey((k) => k + 1);
  };
  const selectConversation = (id: number) => {
    if (id === session?.id) return;
    loadedId.current = null;
    setSession(null);
    setLoadError(false);
    setChatActive(false);
    map.close(false);
    setChatKey((k) => k + 1);
    setSessionId(id);
  };
  // Merge only the title: a running chat owns the rest of the session state.
  const onRenamed = (s: AssistantSession) =>
    setSession((prev) =>
      prev && prev.id === s.id ? { ...prev, title: s.title } : prev,
    );
  // Changing the current spec is a normal POST (no step-up): the header selector.
  const changeSpec = async (spec: string) => {
    if (!session) return;
    try {
      const updated = await api.post<AssistantSession>(
        `/api/assistant/sessions/${session.id}/spec`,
        { spec },
      );
      setSession(updated);
    } catch {
      // Keep the previous spec; the next session poll shows the server's value.
    }
  };

  const content = (
    <>
      <div className="flex min-h-14 shrink-0 flex-wrap items-center gap-1 border-b border-line pl-3 pr-1 sm:h-14 sm:flex-nowrap">
        <span className="mr-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
          <Sparkles className="h-4 w-4" aria-hidden />
        </span>
        {session ? (
          <EditableTitle
            sessionId={session.id}
            title={session.title}
            onRenamed={onRenamed}
            className="min-w-[4rem] flex-1"
          >
            <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
              {session.title}
            </h2>
          </EditableTitle>
        ) : (
          <h2 className="min-w-[4rem] flex-1 truncate text-sm font-semibold text-ink">
            {t.assistant.panelTitle}
          </h2>
        )}
        {!docked && session && session.specs && session.specs.length > 0 ? (
          <div className="order-last w-full pb-2 sm:order-none sm:w-auto sm:shrink-0 sm:pb-0">
            <SpecSelect
              current={session.current_spec ?? null}
              specs={session.specs}
              onChange={(spec) => void changeSpec(spec)}
            />
          </div>
        ) : null}
        {session ? (
          <div
            className="order-last flex w-full min-w-0 pb-2 sm:order-none sm:mr-1 sm:w-auto sm:shrink sm:pb-0"
            data-session-indicator-slot=""
          >
            <SessionIndicator
              session={session}
              working={chatActive}
              onOpen={map.toggle}
            />
          </div>
        ) : null}
        {session ? (
          <button
            type="button"
            className={`${ICON_BUTTON} ${map.open ? "bg-subtle text-ink" : ""}`}
            onClick={(e) => map.toggle(e.currentTarget)}
            aria-label={t.assistant.agentMap.open}
            title={t.assistant.agentMap.open}
            aria-pressed={map.open}
            data-agent-map-toggle=""
          >
            <Network className="h-5 w-5" aria-hidden />
          </button>
        ) : null}
        {session ? (
          <div className="relative">
            <button
              type="button"
              className={ICON_BUTTON}
              aria-label={t.ai.repairMenu}
              title={t.ai.repairMenu}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
              data-conversation-menu=""
            >
              {repairing ? (
                <Wrench className="h-5 w-5 animate-pulse" aria-hidden />
              ) : (
                <MoreHorizontal className="h-5 w-5" aria-hidden />
              )}
            </button>
            {menuOpen ? (
              <div
                role="menu"
                aria-label={t.ai.repairMenu}
                className="absolute right-0 z-30 mt-1 w-60 rounded-xl border border-line bg-surface p-1 shadow-raised"
              >
                <button
                  type="button"
                  role="menuitem"
                  disabled={repairing}
                  onClick={() => void repairConversation()}
                  className="flex min-h-tap w-full items-center rounded-lg px-3 text-left text-sm font-medium text-ink hover:bg-subtle disabled:opacity-50"
                >
                  <Wrench className="mr-2 h-4 w-4 shrink-0" aria-hidden />
                  {repairing ? t.ai.repairing : t.ai.repair}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
        <AssistantHistory
          currentId={session?.id ?? null}
          onSelect={selectConversation}
          onNew={newConversation}
          onRenamed={onRenamed}
        />
        <button
          type="button"
          className={ICON_BUTTON}
          onClick={newConversation}
          aria-label={t.assistant.newConversation}
          title={t.assistant.newConversation}
        >
          <Plus className="h-5 w-5" aria-hidden />
        </button>
        {docked ? (
          <>
            <button
              type="button"
              className={ICON_BUTTON}
              onClick={() => setExpanded(mode !== "expanded")}
              aria-label={
                mode === "expanded"
                  ? t.assistant.collapsePanel
                  : t.assistant.expandPanel
              }
              title={
                mode === "expanded"
                  ? t.assistant.collapsePanel
                  : t.assistant.expandPanel
              }
            >
              {mode === "expanded" ? (
                <Minimize2 className="h-5 w-5" aria-hidden />
              ) : (
                <Maximize2 className="h-5 w-5" aria-hidden />
              )}
            </button>
            <button
              type="button"
              className={ICON_BUTTON}
              onClick={close}
              aria-label={t.assistant.closePanel}
              title={t.assistant.closePanel}
            >
              <X className="h-5 w-5" aria-hidden />
            </button>
          </>
        ) : null}
      </div>

      {session?.draft ? (
        <div className="flex flex-col gap-2 border-b border-line bg-canvas px-4 py-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone={session.validation?.valid ? "success" : "danger"}>
              {session.validation?.valid
                ? t.assistant.valid
                : t.assistant.issues.replace(
                    "{n}",
                    String(session.validation?.errors?.length ?? 0),
                  )}
            </Badge>
            <ReadinessPill ready={!!session.readiness?.ready} />
            <span className="min-w-0 flex-1 truncate text-ink-2">
              {session.draft.summary}
            </span>
            {session.project ? (
              <Link
                to={`/proyectos/${session.project.slug}?chat=${session.id}`}
                onClick={docked ? close : undefined}
                className="font-semibold text-accent underline"
              >
                {t.projects.projectOf(session.project.name)}
              </Link>
            ) : null}
          </div>
          {session.validation?.valid === false &&
          session.validation?.errors?.length ? (
            <details>
              <summary className="min-h-tap cursor-pointer text-sm font-semibold text-danger">
                {t.assistant.showProblems.replace(
                  "{n}",
                  String(session.validation.errors.length),
                )}
              </summary>
              <div className="mt-1 max-h-48 overflow-y-auto">
                <ProblemList problems={session.validation.errors} dense
                             onApplyFix={applyProblemFix} applying={fixing} />
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {proposal ? (
        <ProjectProposal
          text={proposal.text}
          onCreated={(s) => {
            proposal.resolve(s);
            setProposal(null);
          }}
          onCancel={() => {
            proposal.reject(new ApiError(0, "cancelled", ""));
            setProposal(null);
          }}
        />
      ) : null}

      {repairNotice ? (
        <div className="px-3 pt-2 sm:px-4" role="status">
          <Alert tone="success" action={
            <button type="button" onClick={() => setRepairNotice(null)}
                    className="rounded px-1.5 py-0.5 text-xs underline hover:bg-subtle">
              {t.common.close}
            </button>
          }>
            {repairNotice}
          </Alert>
        </div>
      ) : null}

      <div data-chat-area="" className="flex min-h-0 flex-1 flex-col">
        {loadError && !session ? (
          <p className="flex flex-1 items-center justify-center p-6 text-center text-sm text-ink-2">
            {t.assistant.failedToLoadSession}
          </p>
        ) : (
          <AssistantChat
            key={chatKey}
            variant={docked ? "panel" : "page"}
            session={session}
            onSession={onSession}
            createSession={(text) =>
              new Promise<AssistantSession>((resolve, reject) =>
                setProposal({ text, resolve, reject }),
              )
            }
            autoFocus
            onActivityChange={setChatActive}
            onOpenFile={
              session?.project
                ? (path) =>
                    navigate(
                      `/proyectos/${session.project!.slug}?file=${encodeURIComponent(path)}`,
                    )
                : undefined
            }
            mapOverlay={
              map.open && session ? (
                <AgentMapOverlay
                  sessionId={session.id}
                  title={session.title}
                  busy={chatActive || !!session.busy}
                  onClose={() => map.close()}
                  placement="chat"
                />
              ) : null
            }
            onToggleMap={session ? map.toggle : undefined}
            mapOpen={map.open}
          />
        )}
      </div>
    </>
  );

  if (!docked) {
    return (
      <section
        aria-label={t.assistant.panelTitle}
        className="flex h-[calc(100vh-11rem)] min-h-[28rem] flex-col rounded-2xl border border-line bg-surface"
      >
        {content}
      </section>
    );
  }
  const dockedInPlace = mode !== "expanded";
  const place = dockedInPlace
      // The seam is the IDE's own divider — `w-1.5 bg-line`, the element between the file explorer
      // and the editor — painted as a real 0.375 rem strip inside the panel's left edge, in rem so
      // it follows the type scale like the divider does. The panel used to carry a 1 px border plus
      // `shadow-raised`, whose halo spilled ~10 px into the page and read as empty space (owner,
      // 2026-10-15: "the space between chat and [the page] is exaggerated — use the same space as
      // between the file explorer and the result view").
      ? "pl-1.5"
      : `${chromeHidden ? "left-0" : "left-64"} z-30`;
  return (
    <aside
      ref={asideRef}
      id="assistant-panel"
      aria-label={t.assistant.panelTitle}
      /* The panel owns the full height of its own column (feature 025): starting below the top bar
         left a band of empty canvas above it, because the top bar only spans the content column. */
      style={dockedInPlace ? { width: `${width}px` } : undefined}
      className={`fixed inset-y-0 right-0 z-40 hidden flex-col bg-surface lg:flex ${place}`}
    >
      {dockedInPlace ? (
        <PanelResizer width={width} onResize={setWidth} label={t.assistant.resizePanel} />
      ) : null}
      {content}
    </aside>
  );
}

export function AssistantPanel() {
  const { mode } = useAssistantPanel();
  const { ai_enabled } = useBranding();
  if (mode === "closed" || !ai_enabled) return null;
  return <AssistantView placement="docked" />;
}
