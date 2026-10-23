import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { Download, GitBranch, History, Maximize2, Minimize2, Pencil, Play, Sparkles, Trash2, Undo2, Upload } from "lucide-react";
import { api, ApiError } from "../../api/client";
import { isRevisionGroup, projectsApi } from "../../api/projects";
import type {
  AssistantSession, FileChangedCurrent, ProjectCheck, ProjectDetail, ProjectStatus, ProjectTree,
} from "../../api/types";
import { AssistantChat } from "../../components/assistant/AssistantChat";
import { SpecSelect } from "../../components/assistant/SpecSelect";
import { BackLink } from "../../components/BackLink";
import { PreviewReports } from "../../components/assistant/PreviewReports";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Spinner } from "../../components/Spinner";
import { useAssistantPanel } from "../../components/assistant/AssistantPanelContext";
import { useHideShellChrome } from "../../components/ShellChrome";
import { useToast } from "../../components/Toast";
import { CodeEditor, type CodeEditorHandle } from "../../components/ide/CodeEditor";
import { ConflictBar } from "../../components/ide/ConflictBar";
import { DiffView } from "../../components/ide/DiffView";
import { EditorTabs, openTab, type OpenTab } from "../../components/ide/EditorTabs";
import { Explorer } from "../../components/ide/Explorer";
import { MarkdownView } from "../../components/ide/MarkdownView";
import { PaneTabs, useWideLayout, type PaneId } from "../../components/ide/PaneTabs";
import { ProblemsPanel } from "../../components/ide/ProblemsPanel";
import { StatusBar, type SaveState } from "../../components/ide/StatusBar";
import { useLeaveGuard } from "../../components/ide/useLeaveGuard";
import { useProjectChanges } from "../../components/ide/useProjectChanges";
import { useBranding } from "../../config/BrandingContext";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import {
  enterFullscreen, exitFullscreen, fullscreenSupported, isFullscreen, onFullscreenChange,
} from "../../lib/fullscreen";
import { lineDiff } from "../../lib/lineDiff";

interface Buffer {
  content: string;
  saved: string;
  sha: string | null;
  rendered: boolean;
  conflict?: { kind: "stale" | "disk"; current: FileChangedCurrent | null };
}

type Confirm = "apply" | "withdraw" | "delete" | "convert";

const STATUS_TONE: Record<ProjectStatus, "gray" | "green" | "amber" | "red"> = {
  borrador: "gray", aplicado: "green", cambios: "amber", retirado: "red",
};

const errorText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const FIELD = "min-h-tap w-full rounded-card border border-line bg-surface px-3 text-sm text-ink "
  + "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-60";

/** One flat control of the project toolbar: same height and type as its neighbours, divided by a
 * hairline, and a touch target that grows under a finger (`control-compact`). */
function ToolButton(props: {
  icon: ReactNode;
  label: string;
  title?: string;
  pressed?: boolean;
  disabled?: boolean;
  /** Tool strips: the icon alone, with the words in the tooltip and the accessible name. */
  iconOnly?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={props.iconOnly ? props.label : undefined}
      aria-pressed={props.pressed}
      title={props.title ?? props.label}
      disabled={props.disabled}
      onClick={props.onClick}
      className={`control-compact inline-flex items-center justify-center gap-1.5 border-l border-line text-sm font-medium transition-colors first:border-l-0 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 disabled:cursor-not-allowed disabled:text-ink-faint ${
        props.iconOnly ? "min-w-tap" : "px-3"
      } ${
        props.pressed
          ? "bg-subtle text-accent-strong"
          : "text-ink-2 hover:bg-subtle hover:text-ink"
      }`}
    >
      {props.icon}
      {props.iconOnly ? <span className="sr-only">{props.label}</span> : props.label}
    </button>
  );
}

export function ProjectWorkspace() {
  const t = useT();
  const { slug = "" } = useParams<{ slug: string }>();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { ai_enabled } = useBranding();
  // Feature 024 polish: the whole project on the whole screen — the app chrome steps aside and the
  // browser hides its own bars, so the files, the editor and the chat get every pixel back.
  const full = search.get("full") === "1";
  const canFullscreen = fullscreenSupported();
  useHideShellChrome(full);
  const setFull = useCallback(
    (on: boolean) => {
      const next = new URLSearchParams(search);
      if (on) next.set("full", "1");
      else next.delete("full");
      setSearch(next, { replace: true });
      if (on) void enterFullscreen();
      else void exitFullscreen();
    },
    [search, setSearch],
  );
  useEffect(() => {
    if (!full) return;
    return onFullscreenChange(() => {
      if (!isFullscreen()) setFull(false);   // Esc leaves the browser full screen: bring the chrome back
    });
  }, [full, setFull]);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [tree, setTree] = useState<ProjectTree | null>(null);
  const [check, setCheck] = useState<ProjectCheck | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pane, setPane] = useState<PaneId>("files");
  // Feature 024 polish: one chat per screen. From 1024 px the docked panel (the same chat as the
  // rest of the app) shows the conversation and the page does not render a second copy of it;
  // below that the chat is a pane, because the panel has no room to dock.
  const wide = useWideLayout();
  const { mode: chatMode, toggle: toggleChat, open: openChat, setSessionId } = useAssistantPanel();
  const chatOpen = chatMode !== "closed";
  const syncedChat = useRef<string | null>(null);
  const [tabs, setTabs] = useState<OpenTab[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [buffers, setBuffers] = useState<Record<string, Buffer>>({});
  const [save, setSave] = useState<SaveState>("idle");
  const [notice, setNotice] = useState<string | null>(null);
  const [closing, setClosing] = useState<string | null>(null);
  const [pendingLine, setPendingLine] = useState<number | null>(null);
  const [diff, setDiff] = useState<{ path: string; mine: string; theirs: string } | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [acting, setActing] = useState(false);
  const [result, setResult] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [appliedReports, setAppliedReports] = useState<string[] | null>(null);
  const [details, setDetails] = useState<{ name: string; description: string; slug: string } | null>(null);
  const [savingDetails, setSavingDetails] = useState(false);
  /** Where the user wanted to go while tabs were unsaved (020 T083); null when not leaving. */
  const [leaving, setLeaving] = useState<string | null>(null);
  const [session, setSession] = useState<AssistantSession | null>(null);
  const editor = useRef<CodeEditorHandle | null>(null);

  const readOnly = project?.origin === "git";
  const dirty = tabs.some((tab) => tab.dirty);

  const refresh = useCallback(async () => {
    const [detail, files] = await Promise.all([projectsApi.get(slug), projectsApi.tree(slug)]);
    setProject(detail);
    setTree(files);
  }, [slug]);

  const [checking, setChecking] = useState(false);
  const revalidate = useCallback(async () => {
    setChecking(true);
    try {
      setCheck(await projectsApi.validate(slug));
    } catch {
      /* the problems panel keeps the last result */
    } finally {
      setChecking(false);
    }
  }, [slug]);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    refresh().then(() => { if (!cancelled) void revalidate(); })
      .catch((e) => !cancelled && setLoadError(errorText(e, t.common.unexpected)));
    return () => { cancelled = true; };
  }, [refresh, revalidate, t]);

  // Conversation of the chat pane: ?chat=<id>, else the viewer's latest one in the project.
  const chatId = search.get("chat") ?? (project?.conversations[0] ? String(project.conversations[0].id) : null);
  // A deep link (?chat=<id>, what the project history and the old assistant links use) selects the
  // conversation in the docked panel too, so the link opens what the user asked for.
  useEffect(() => {
    if (!wide || !chatId || syncedChat.current === chatId) return;
    syncedChat.current = chatId;
    setSessionId(Number(chatId));
    openChat();
  }, [wide, chatId, setSessionId, openChat]);

  useEffect(() => {
    if (!chatId) { setSession(null); return; }
    let cancelled = false;
    api.get<AssistantSession>(`/api/assistant/sessions/${chatId}`)
      .then((s) => !cancelled && setSession(s))
      .catch(() => !cancelled && setSession(null));
    return () => { cancelled = true; };
  }, [chatId]);

  useLeaveGuard(dirty, setLeaving);

  const setBuffer = (path: string, change: Partial<Buffer> | ((b: Buffer) => Partial<Buffer>)) =>
    setBuffers((prev) => {
      const current = prev[path];
      if (!current) return prev;
      return { ...prev, [path]: { ...current, ...(typeof change === "function" ? change(current) : change) } };
    });
  const markDirty = (path: string, isDirty: boolean) =>
    setTabs((prev) => prev.map((tab) => (tab.path === path ? { ...tab, dirty: isDirty } : tab)));

  const load = async (path: string) => {
    const file = await projectsApi.file(slug, path);
    setBuffers((prev) => ({ ...prev, [path]: { content: file.content, saved: file.content,
                                               sha: file.sha256, rendered: path.endsWith(".md") } }));
    markDirty(path, false);
  };

  const openFile = async (path: string, line: number | null = null) => {
    const next = openTab(tabs, path);
    if (next.refused) { setNotice(t.projects.tooManyTabs); return; }
    setNotice(null);
    const dropped = tabs.filter((tab) => !next.tabs.some((n) => n.path === tab.path)).map((tab) => tab.path);
    setTabs(next.tabs);
    if (dropped.length) setBuffers((prev) => {
      const copy = { ...prev };
      dropped.forEach((p) => delete copy[p]);
      return copy;
    });
    setActive(path);
    setPane("editor");
    if (line) {
      setBuffer(path, { rendered: false });
      setPendingLine(line);
    }
    if (!buffers[path]) {
      try {
        await load(path);
        if (line) setBuffer(path, { rendered: false });
      } catch (e) {
        setNotice(errorText(e, t.common.unexpected));
      }
    }
  };

  // ?file=<path>&line=<n> (links from problems, history and other pages).
  const fileParam = search.get("file");
  useEffect(() => {
    if (!fileParam || !tree) return;
    void openFile(fileParam, Number(search.get("line")) || null);
    const next = new URLSearchParams(search);
    next.delete("file");
    next.delete("line");
    setSearch(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileParam, tree]);

  useEffect(() => {
    if (pendingLine && active && buffers[active] && !buffers[active].rendered) {
      const id = window.setTimeout(() => { editor.current?.goToLine(pendingLine); setPendingLine(null); }, 0);
      return () => window.clearTimeout(id);
    }
  }, [pendingLine, active, buffers]);

  const conflictCurrent = async (path: string): Promise<FileChangedCurrent | null> => {
    try {
      const first = (await projectsApi.history(slug, { path })).items.find(isRevisionGroup);
      return first ? { revision_id: first.files[0]?.id ?? null, sha256: first.files[0]?.sha256 ?? null,
                       author: first.actor_name ?? first.actor, time: first.time } : null;
    } catch {
      return null;
    }
  };

  const saveFile = async (path: string, force = false): Promise<boolean> => {
    const buffer = buffers[path];
    if (!buffer || readOnly) return false;
    setSave("saving");
    try {
      const res = await projectsApi.save(slug, { path, content: buffer.content, base_sha256: buffer.sha, force });
      setBuffer(path, (b) => ({ saved: buffer.content, sha: res.file.sha256, conflict: undefined,
                                content: b.content }));
      markDirty(path, buffers[path].content !== buffer.content);
      setCheck({ validation: res.validation, readiness: res.readiness });
      setSave("saved");
      setTree(await projectsApi.tree(slug));
      return true;
    } catch (e) {
      setSave("dirty");
      if (e instanceof ApiError && e.code === "file_changed") {
        setBuffer(path, { conflict: { kind: "stale", current: await conflictCurrent(path) } });
      } else {
        setNotice(errorText(e, t.common.unexpected));
      }
      return false;
    }
  };

  const saveAndLeave = async (to: string) => {
    const results = [];
    for (const tab of tabs.filter((item) => item.dirty)) results.push(await saveFile(tab.path));
    if (results.every(Boolean)) navigate(to);
    else setLeaving(null);              // a conflict or error is shown on its tab
  };

  const showDiff = async (path: string) => {
    try {
      const theirs = (await projectsApi.file(slug, path)).content;
      setDiff({ path, mine: buffers[path]?.content ?? "", theirs });
    } catch (e) {
      setNotice(errorText(e, t.common.unexpected));
    }
  };

  const closeTab = (path: string, force = false) => {
    if (!force && tabs.find((tab) => tab.path === path)?.dirty) { setClosing(path); return; }
    const rest = tabs.filter((tab) => tab.path !== path);
    setTabs(rest);
    setBuffers((prev) => {
      const copy = { ...prev };
      delete copy[path];
      return copy;
    });
    if (active === path) setActive(rest[rest.length - 1]?.path ?? null);
    setClosing(null);
  };

  const { busy } = useProjectChanges(slug, {
    enabled: !!project,
    onChanges: (paths, isBusy) => {
      if (!paths.length) { if (!isBusy) void revalidate(); return; }
      void projectsApi.tree(slug).then(setTree).catch(() => undefined);
      for (const path of paths) {
        const tab = tabs.find((item) => item.path === path);
        if (!tab) continue;
        if (tab.dirty) setBuffer(path, { conflict: { kind: "disk", current: null } });
        else void load(path).catch(() => closeTab(path, true));
      }
      if (!isBusy) void revalidate();
    },
  });

  const op = async (ops: Record<string, unknown>[]): Promise<string | null> => {
    try {
      const res = await projectsApi.ops(slug, ops);
      setCheck({ validation: res.validation, readiness: res.readiness });
      setTree(await projectsApi.tree(slug));
      return null;
    } catch (e) {
      return errorText(e, t.common.unexpected);
    }
  };
  const shaOf = (path: string) => tree?.files.find((f) => f.path === path)?.sha256 ?? null;

  // 020 T087: name and description any time; the identifier only while never applied.
  const saveDetails = async (e: FormEvent) => {
    e.preventDefault();
    if (!details || !project) return;
    setSavingDetails(true);
    setResult(null);
    try {
      const body: { name: string; description: string; slug?: string } = {
        name: details.name.trim(), description: details.description.trim(),
      };
      if (!project.first_applied_at && details.slug !== project.slug) body.slug = details.slug;
      const updated = await projectsApi.update(slug, body);
      setProject(updated);
      setDetails(null);
      if (updated.slug !== slug) navigate(`/proyectos/${updated.slug}`, { replace: true });
    } catch (err) {
      setResult({ tone: "error", text: errorText(err, t.common.unexpected) });
    } finally {
      setSavingDetails(false);
    }
  };

  const act = async (kind: Confirm) => {
    setActing(true);
    setResult(null);
    setAppliedReports(null);
    try {
      if (kind === "apply") {
        const res = await projectsApi.apply(slug);
        setProject(res.project);
        setResult({ tone: "success", text: `${t.projects.applied(res.version.id)}${res.revalidated ? ` ${t.projects.revalidated}` : ""}` });
        setAppliedReports(res.version.projects?.[slug]?.reports ?? []);
      } else if (kind === "withdraw") {
        const res = await projectsApi.withdraw(slug);
        setProject(res.project);
        setResult({ tone: "success", text: t.projects.withdrawn(res.version.id) });
      } else if (kind === "convert") {
        setProject(await projectsApi.convert(slug));
        setResult({ tone: "success", text: t.projects.converted });
      } else {
        await projectsApi.remove(slug);
        toast(t.projects.deleted);
        navigate("/proyectos");
        return;
      }
      void revalidate();
    } catch (e) {
      setResult({ tone: "error", text: errorText(e, t.common.unexpected) });
    } finally {
      setActing(false);
      setConfirm(null);
    }
  };

  const preview = async () => {
    try {
      await projectsApi.requestPreview(slug);
      if (wide) toggleChat();
      else setPane("chat");
      toast(t.projects.preview);
    } catch (e) {
      setResult({ tone: "error", text: errorText(e, t.common.unexpected) });
    }
  };

  const pickConversation = (id: string) => {
    const next = new URLSearchParams(search);
    next.set("chat", id);
    setSearch(next, { replace: true });
  };
  const newConversation = async () => {
    try {
      const s = await projectsApi.createSession(slug);
      setSession(s);
      pickConversation(String(s.id));
      setProject(await projectsApi.get(slug));
    } catch (e) {
      setResult({ tone: "error", text: errorText(e, t.common.unexpected) });
    }
  };
  const setSpec = async (folder: string) => {
    if (!session) return;
    try {
      setSession(await projectsApi.setCurrentSpec(session.id, folder));
    } catch (e) {
      setResult({ tone: "error", text: errorText(e, t.common.unexpected) });
    }
  };

  const activeBuffer = active ? buffers[active] : undefined;
  const fileProblems = useMemo(
    () => (check?.validation.errors ?? []).filter((p) => p.file === active && (!p.project || p.project === slug)),
    [check, active, slug],
  );
  const specOfActive = active?.match(/^specs\/(\d{3}-[^/]+)\/spec\.md$/)?.[1];
  const specInfo = specOfActive ? project?.specs.find((s) => s.folder === specOfActive) : undefined;

  if (loadError) {
    return <div className="space-y-4"><BackLink to="/proyectos" className="mb-0" />
      <Alert tone="error">{loadError}</Alert></div>;
  }
  if (!project || !tree) {
    return <div role="status" className="flex justify-center py-12 text-accent"><Spinner className="h-8 w-8" /><span className="sr-only">{t.common.loading}</span></div>;
  }

  const confirmText: Record<Confirm, string> = {
    apply: t.projects.applyConfirm, withdraw: t.projects.withdrawConfirm,
    delete: t.projects.deleteConfirm, convert: t.projects.convertConfirm,
  };
  const applied = project.status === "aplicado" || project.status === "cambios";
  const changes = project.changed_files;

  const filesPane = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <Explorer
          tree={tree}
          activePath={active}
          readOnly={readOnly}
          onOpen={(path) => void openFile(path)}
          onCreate={async (path, folder) => {
            if (folder) return op([{ op: "mkdir", path }]);
            try {
              const res = await projectsApi.save(slug, { path, content: "", base_sha256: null });
              setCheck({ validation: res.validation, readiness: res.readiness });
              setTree(await projectsApi.tree(slug));
              void openFile(path);
              return null;
            } catch (e) {
              return errorText(e, t.common.unexpected);
            }
          }}
          onRename={(from, to) => op([{ op: "rename", from, to, base_sha256: shaOf(from) }])}
          onDelete={(path, folder) => {
            if (!folder) closeTab(path, true);
            return op(folder ? [{ op: "rmdir", path }] : [{ op: "delete", path, base_sha256: shaOf(path) }]);
          }}
        />
      </div>
      <div className="max-h-[45%] min-h-[8rem] border-t border-line">
        <ProblemsPanel validation={check?.validation ?? null} slug={slug}
                       onOpen={(file, line) => void openFile(file, line)}
                       onRevalidate={() => void revalidate()} checking={checking} />
      </div>
    </div>
  );

  const editorPane = (
    <div className="flex h-full min-h-0 flex-col">
      <EditorTabs
        tabs={tabs}
        active={active}
        onSelect={setActive}
        onClose={(path) => closeTab(path)}
        closing={closing}
        onSaveClose={async () => { if (closing && (await saveFile(closing))) closeTab(closing, true); }}
        onDiscardClose={() => closing && closeTab(closing, true)}
        onCancelClose={() => setClosing(null)}
        notice={notice}
      />
      {active && activeBuffer?.conflict && (
        <ConflictBar
          kind={activeBuffer.conflict.kind}
          current={activeBuffer.conflict.current}
          onDiff={() => void showDiff(active)}
          onOverwrite={() => void saveFile(active, true)}
          onReload={() => void load(active)}
          onDiscard={() => void load(active)}
        />
      )}
      {diff && (
        <section className="max-h-[40%] overflow-auto border-b border-line" aria-label={t.projects.diffTitle(diff.path)}>
          <div className="flex items-center justify-between bg-subtle px-3 py-1.5 text-sm font-semibold text-ink">
            {t.projects.diffTitle(diff.path)}
            <Button variant="ghost" onClick={() => setDiff(null)}>{t.projects.cancel}</Button>
          </div>
          <DiffView hunks={lineDiff(diff.theirs, diff.mine)} truncated={false} caption={t.projects.diffTitle(diff.path)} />
        </section>
      )}
      <div className="min-h-0 flex-1">
        {!active || !activeBuffer ? (
          <p className="p-6 text-sm text-ink-muted">{t.projects.noFileOpen}</p>
        ) : activeBuffer.rendered ? (
          <MarkdownView
            text={activeBuffer.content}
            onShowCode={() => setBuffer(active, { rendered: false })}
            header={specInfo && (
              <span className="flex flex-wrap items-center gap-1.5">
                {specInfo.kind && <Badge tone="blue">{t.projects.kind[specInfo.kind]}</Badge>}
                {specInfo.stage && <Badge tone="gray">{t.projects.stage[specInfo.stage]}</Badge>}
                {specInfo.converged && <Badge tone="amber">{t.projects.converged}</Badge>}
                {specInfo.source_missing && (
                  <Link to={specInfo.source_missing.link} className="text-xs text-accent underline">
                    {t.projects.sourceMissing(specInfo.source_missing.source ?? "?")} · {t.projects.registerSource}
                  </Link>
                )}
              </span>
            )}
          />
        ) : (
          <div className="flex h-full min-h-0 flex-col">
            {active.endsWith(".md") && (
              <div className="flex justify-end border-b border-line bg-subtle px-3 py-1">
                <Button variant="ghost" onClick={() => setBuffer(active, { rendered: true })}>{t.projects.viewRendered}</Button>
              </div>
            )}
            <div className="min-h-0 flex-1">
              <CodeEditor
                key={active}
                ref={editor}
                value={activeBuffer.content}
                path={active}
                readOnly={readOnly}
                problems={fileProblems}
                ariaLabel={active}
                onChange={(value) => {
                  setBuffer(active, { content: value });
                  markDirty(active, value !== activeBuffer.saved);
                  setSave(value !== activeBuffer.saved ? "dirty" : "idle");
                }}
                onSave={() => void saveFile(active)}
              />
            </div>
          </div>
        )}
      </div>
      {active && !readOnly && activeBuffer && !activeBuffer.rendered && (
        <div className="flex justify-end gap-2 border-t border-line px-3 py-1.5">
          <Button disabled={!tabs.find((tab) => tab.path === active)?.dirty} loading={save === "saving"}
                  onClick={() => void saveFile(active)}>
            {t.projects.save}
          </Button>
        </div>
      )}
    </div>
  );

  const conversations = project.conversations;
  const chatPane = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-subtle p-2">
        <label className="sr-only" htmlFor="project-chat">{t.projects.conversation}</label>
        {conversations.length > 0 && (
          <select id="project-chat" value={session ? String(session.id) : ""}
                  onChange={(e) => pickConversation(e.target.value)}
                  className="min-h-tap min-w-0 flex-1 rounded-card border border-line bg-surface px-2 text-sm text-ink">
            {conversations.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        )}
        {ai_enabled && (
          <Button variant="secondary" onClick={() => void newConversation()}>{t.projects.newChat}</Button>
        )}
        {session && project.specs.length > 0 && (
          <SpecSelect
            current={session.current_spec ?? null}
            specs={project.specs}
            onChange={(folder) => void setSpec(folder)}
          />
        )}
      </div>
      {!ai_enabled && <div className="p-2"><Alert tone="info">{t.projects.aiOff}</Alert></div>}
      {session?.read_only && <div className="p-2"><Alert tone="warning">{t.projects.readOnlyChat}</Alert></div>}
      {ai_enabled && (
        <div className="min-h-0 flex-1">
          <AssistantChat
            session={session}
            onSession={(s) => setSession(s)}
            createSession={async () => {
              const s = await projectsApi.createSession(slug);
              pickConversation(String(s.id));
              return s;
            }}
            variant="page"
            onOpenFile={(path) => void openFile(path)}
          />
        </div>
      )}
    </div>
  );

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-[32rem] flex-col gap-3">
      {/* One row from 1024 px (the title truncates, the actions keep their size); on phones the
          tool strip wraps under the title instead of pushing the page sideways. */}
      {/* The header sticks right below the top bar (or at the very top in full screen): a long page
          never takes the project's actions away — and nothing ends up half-hidden under the bar. */}
      <header
        className={`sticky ${full ? "top-0" : "top-14 sm:top-16"} z-20 flex shrink-0 flex-wrap items-center gap-2 bg-canvas lg:flex-nowrap`}
      >
        <BackLink to="/proyectos" className="mb-0 shrink-0"
                  onNavigate={(e) => { if (dirty) { e.preventDefault(); setLeaving("/proyectos"); } }} />
        {/* The identity block shrinks and truncates; the actions keep their size. */}
        <div className="flex min-w-0 flex-1 items-center gap-2 lg:flex-1">
        {/* The title carries the identity; renaming is a quiet icon next to it (the pencil is
            still a button with its own name, so it stays reachable by keyboard and reader). */}
        <h1 className="min-w-0 truncate text-lg font-semibold tracking-tight text-ink">{project.name}</h1>
        {!readOnly && !details && (
          <button
            type="button"
            aria-label={t.projects.editDetails}
            title={t.projects.editDetails}
            onClick={() => setDetails({ name: project.name, description: project.description,
                                        slug: project.slug })}
            className="control-compact -ml-1 inline-flex shrink-0 items-center justify-center rounded-lg px-2 text-ink-faint transition-colors hover:bg-subtle hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2"
          >
            <Pencil className="h-3.5 w-3.5" aria-hidden />
          </button>
        )}
        <Badge tone={STATUS_TONE[project.status]} className="shrink-0">{t.projects.status[project.status]}</Badge>
        {project.origin === "git" && <Badge tone="blue" className="shrink-0" icon={<GitBranch className="h-3.5 w-3.5" aria-hidden />}>{t.projects.origin.git}</Badge>}
        </div>
        {/* Phones: the actions take the row and wrap among themselves; desktop: they sit on the
            title's line and never wrap. */}
        <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:shrink-0 lg:flex-nowrap">
          {/* Tool strip (feature 024 polish): one bordered group of flat icon controls — the words
              live in the tooltip and the accessible name — the primary action standing out on its
              own, and the destructive one quiet instead of a red block. */}
          <div className="flex items-stretch overflow-hidden rounded-lg border border-line bg-surface">
            <ToolButton iconOnly icon={<Play className="h-4 w-4" aria-hidden />} label={t.projects.preview}
                        onClick={() => void preview()} />
            {ai_enabled && wide ? (
              // One chat per screen: opens/closes the docked panel from the project itself, so the
              // chat is reachable in full screen too (the top bar is hidden there). The label is
              // stable and `aria-pressed` carries the state.
              <ToolButton iconOnly icon={<Sparkles className="h-4 w-4" aria-hidden />}
                          label={t.assistant.panelTitle} pressed={chatOpen}
                          title={chatOpen ? t.assistant.closePanel : t.assistant.openPanel}
                          onClick={() => toggleChat()} />
            ) : null}
            {canFullscreen ? (
              <ToolButton iconOnly
                          icon={full ? <Minimize2 className="h-4 w-4" aria-hidden />
                                     : <Maximize2 className="h-4 w-4" aria-hidden />}
                          label={full ? t.projects.exitFullscreen : t.projects.fullscreen}
                          pressed={full} onClick={() => setFull(!full)} />
            ) : null}
            <a href={projectsApi.exportUrl(slug)} download aria-label={t.projects.download}
               title={t.projects.download}
               className="control-compact inline-flex min-w-tap items-center justify-center border-l border-line text-ink-2 transition-colors hover:bg-subtle hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2">
              <Download className="h-4 w-4" aria-hidden />
            </a>
            <Link to={`/proyectos/${slug}/historial`} aria-label={t.projects.history}
                  title={t.projects.history}
                  className="control-compact inline-flex min-w-tap items-center justify-center border-l border-line text-ink-2 transition-colors hover:bg-subtle hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2">
              <History className="h-4 w-4" aria-hidden />
            </Link>
          </div>
          {!readOnly && (
            // On phones the label is in the accessible name only: the header must stay two rows so
            // the page fits the viewport and nothing slides under the sticky top bar.
            // A disabled primary action explains itself (owner, 2026-10-23: "idk how to apply"):
            // the first pending item is the reason the backend gives, already localized.
            <Button size="sm" icon={<Upload className="h-4 w-4" aria-hidden />}
                    aria-label={t.projects.apply}
                    title={dirty ? t.projects.saveFirstToApply
                      : !check?.readiness.ready
                        ? [t.projects.notReady, ...(check?.readiness.pending ?? [])
                            .map((item) => item.message)].join(": ")
                        : undefined}
                    disabled={!check?.readiness.ready || dirty} onClick={() => setConfirm("apply")}>
              <span className="hidden sm:inline">{t.projects.apply}</span>
            </Button>
          )}
          {applied && (
            <Button size="sm" variant="secondary" icon={<Undo2 className="h-4 w-4" aria-hidden />}
                    onClick={() => setConfirm("withdraw")}>
              {t.projects.withdraw}
            </Button>
          )}
          {readOnly ? (
            <Button size="sm" variant="secondary" onClick={() => setConfirm("convert")}>{t.projects.convert}</Button>
          ) : !applied && (
            <button
              type="button"
              aria-label={t.projects.deleteProject}
              title={t.projects.deleteProject}
              onClick={() => setConfirm("delete")}
              className="control-compact inline-flex min-w-tap items-center justify-center rounded-lg text-danger-strong transition-colors hover:bg-danger-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
            </button>
          )}
        </div>
      </header>

      {details && (
        <form onSubmit={(e) => void saveDetails(e)} aria-label={t.projects.editDetails}
              className="grid gap-2 rounded-card border border-line bg-surface p-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm font-semibold text-ink-2">
            <span>{t.projects.name}</span>
            <input className={FIELD} value={details.name} maxLength={80} required
                   onChange={(e) => setDetails({ ...details, name: e.target.value })} />
          </label>
          <label className="space-y-1 text-sm font-semibold text-ink-2">
            <span>{t.projects.slug}</span>
            <input className={`${FIELD} font-mono`} value={details.slug} maxLength={50}
                   pattern="[a-z][a-z0-9\-]{1,49}" disabled={!!project.first_applied_at}
                   aria-describedby={project.first_applied_at ? "slug-locked" : undefined}
                   onChange={(e) => setDetails({ ...details, slug: e.target.value })} />
            {project.first_applied_at && (
              <span id="slug-locked" className="block text-xs font-normal text-ink-muted">{t.projects.slugLockedHint}</span>
            )}
          </label>
          <label className="space-y-1 text-sm font-semibold text-ink-2 sm:col-span-2">
            <span>{t.projects.description}</span>
            <textarea className={`${FIELD} py-2`} rows={2} maxLength={500} value={details.description}
                      onChange={(e) => setDetails({ ...details, description: e.target.value })} />
          </label>
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button type="submit" loading={savingDetails} disabled={!details.name.trim()}>{t.projects.save}</Button>
            <Button variant="ghost" onClick={() => setDetails(null)}>{t.projects.cancel}</Button>
          </div>
        </form>
      )}
      {leaving && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-card border border-warning-line bg-warning-soft p-2 text-sm text-warning-deep">
          <span className="flex-1">{t.projects.unsavedLeave}</span>
          {!readOnly && (
            <Button onClick={() => void saveAndLeave(leaving)}>{t.projects.saveAndLeave}</Button>
          )}
          <Button variant="danger" onClick={() => navigate(leaving)}>{t.projects.leaveAnyway}</Button>
          <Button variant="ghost" onClick={() => setLeaving(null)}>{t.projects.cancel}</Button>
        </div>
      )}
      {readOnly && <Alert tone="info">{t.projects.gitBanner}</Alert>}
      {confirm && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-card border border-line-accent bg-accent-soft p-3 text-sm text-ink">
          <span className="min-w-0 flex-1">{confirmText[confirm]}</span>
          <Button variant={confirm === "delete" ? "danger" : "primary"} loading={acting} onClick={() => void act(confirm)}>
            {t.projects.confirm}
          </Button>
          <Button variant="ghost" onClick={() => setConfirm(null)}>{t.projects.cancel}</Button>
        </div>
      )}
      {result && <Alert tone={result.tone}>{result.text}</Alert>}
      {appliedReports && appliedReports.length > 0 && (
        <nav aria-label={t.projects.appliedDashboards} className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold text-ink-2">{t.projects.appliedDashboards}</span>
          {appliedReports.map((id) => (
            <Link key={id} to={`/r/${encodeURIComponent(id)}`} className="font-mono text-accent underline">{id}</Link>
          ))}
        </nav>
      )}
      {project.status === "cambios" && (
        <details className="rounded-card border border-warning-line bg-warning-soft p-2 text-sm text-warning-deep">
          <summary className="cursor-pointer font-semibold">{t.projects.changedSinceApplied}</summary>
          <ul className="mt-1 space-y-0.5">
            {([["added", changes.added], ["changed", changes.changed], ["removed", changes.removed]] as const)
              .flatMap(([kind, paths]) => paths.map((path) => (
                <li key={`${kind}:${path}`} className="flex flex-wrap gap-2">
                  <span className="font-semibold">{t.projects[kind]}</span>
                  <Link className="break-all underline" to={`/proyectos/${slug}/historial?file=${encodeURIComponent(path)}`}>{path}</Link>
                </li>
              )))}
          </ul>
        </details>
      )}
      {session?.preview?.status === "succeeded" && (
        <details className="rounded-card border border-line bg-surface p-3">
          <summary className="cursor-pointer text-sm font-semibold text-ink">{t.projects.preview}</summary>
          <div className="mt-3">
            <PreviewReports
              base={`/api/projects/${encodeURIComponent(slug)}`}
              reportIds={tree.files.map((f) => f.path.match(/^reports\/([^/]+)\/report\.yaml$/)?.[1])
                .filter((id): id is string => !!id)}
            />
          </div>
        </details>
      )}
      {project.last_applied && project.status === "aplicado" && (
        <p className="text-xs text-ink-muted">
          {t.projects.lastAppliedBy(project.last_applied.version, formatDateTime(project.last_applied.at),
                                    project.last_applied.by)}
        </p>
      )}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-card border border-line bg-surface">
        <div className="min-h-0 flex-1">
          <PaneTabs files={filesPane} editor={editorPane} chat={chatPane} active={pane}
                    onActive={setPane} showChat={!wide} />
        </div>
        {/* Below every pane, so phones see readiness without opening the editor. */}
        <StatusBar validation={check?.validation ?? null} readiness={check?.readiness ?? null}
                   status={project.status} lastApplied={project.last_applied} save={save} busy={busy}
                   onRunPending={readOnly ? undefined : () => void preview()} />
      </div>
    </div>
  );
}
