import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ClipboardEvent,
  type DragEvent,
  type ReactNode,
} from "react";
import {
  ArrowUp,
  BarChart3,
  BookOpen,
  Eye,
  FilePen,
  FileSearch,
  Paperclip,
  ListChecks,
  Loader2,
  NotebookPen,
  ShieldCheck,
  Sparkles,
  Square,
  Wrench,
  X,
} from "lucide-react";
import { api, ApiError } from "../../api/client";
import {
  acceptAttachmentsNotice,
  deleteAttachment,
  uploadAttachment,
} from "../../api/attachments";
import type {
  AssistantMessage,
  AssistantSession,
  Attachment,
  CommandDef,
  CommandRun,
  CommandSuggestionItem,
  SpecChoice,
} from "../../api/types";
import { useBranding } from "../../config/BrandingContext";
import { useOptionalUser } from "../../auth/AuthContext";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { BudgetNotice } from "./BudgetNotice";
import { ChatText } from "./ChatText";
import { useAssistantPanelOptional } from "./AssistantPanelContext";
import { CommandMenu, filterCommands, menuQuery } from "./CommandMenu";
import { CommandRunChip } from "./CommandRunChip";
import { CommandSuggestions, inlineSuggestions } from "./CommandSuggestion";
import { SpecPicker } from "./SpecPicker";
import { useCommands } from "./useCommands";
import { RunStatus } from "./RunStatus";
import {
  isAssistantBusy,
  isAssistantCapacity,
  useAssistantBusy,
} from "./useAssistantBusy";

const TOOL_ICONS: Record<string, typeof Wrench> = {
  run_preview: Eye,
  update_notes: NotebookPen,
  check_query: ShieldCheck,
  get_authoring_guide: BookOpen,
  edit_draft: FilePen,
  propose_draft: FilePen,
  read_draft: FileSearch,
  profile_source: BarChart3,
};

/** Transcript + composer shared by the docked panel and the full Asistente page (feature 014). */
export function AssistantChat(props: {
  session: AssistantSession | null;
  onSession: (s: AssistantSession) => void;
  /** Creates the conversation on the first message when there is none yet (panel). The
   * docked panel first asks which project the message belongs to (feature 020). */
  createSession?: (firstMessage: string) => Promise<AssistantSession>;
  variant?: "page" | "panel";
  autoFocus?: boolean;
  onActivityChange?: (active: boolean) => void;
  mapOverlay?: ReactNode;
  onToggleMap?: (opener: HTMLElement) => void;
  mapOpen?: boolean;
  /** Opens a project file in the 020 editor (command run chips). */
  onOpenFile?: (path: string) => void;
}) {
  const t = useT();
  const {
    session,
    onSession,
    createSession,
    variant = "page",
    autoFocus,
    onActivityChange,
    mapOverlay,
    onToggleMap,
    mapOpen,
    onOpenFile,
  } = props;
  const { ai_enabled, vision_enabled, attachments_max_mb, attachments_max_per_message } =
    useBranding();
  const user = useOptionalUser();
  const [text, setText] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Feature 024: the image briefs waiting to be sent with the message.
  const [images, setImages] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [noticeAccepted, setNoticeAccepted] = useState(false);
  const [dragging, setDragging] = useState(false);
  const filesRef = useRef<HTMLInputElement | null>(null);
  const maxImages = attachments_max_per_message ?? 4;
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const composerId = useId();
  const menuId = useId();
  const { busy, markBusy, release } = useAssistantBusy(session, onSession);
  // Feature 021: the `/` menu, command chips, suggestions and the inline spec picker.
  // 023: the Ayuda page opens the panel with `/ayuda <tema>` ready in the composer.
  const panel = useAssistantPanelOptional();
  useEffect(() => {
    if (!panel?.draft) return;
    const pending = panel.takeDraft();
    if (pending) setText(pending);   // placed, never sent: the user sends it (no auto-focus either)
  }, [panel]);
  const commands = useCommands(
    text.startsWith("/") ||
      (session?.messages ?? []).some((m) => m.role === "assistant" && m.content.includes("`/")),
  );
  const [caret, setCaret] = useState(0);
  const [activeIndex, setActiveIndex] = useState(0);
  const [menuClosed, setMenuClosed] = useState(false);
  const [hint, setHint] = useState<CommandDef | null>(null);
  const [picker, setPicker] = useState<{ command: string; specs: SpecChoice[]; text: string } | null>(null);
  const [unknown, setUnknown] = useState<string[] | null>(null);
  const [activeConflict, setActiveConflict] = useState(false);
  /**
   * Opt-in pipeline (never automatic): one press sends `/speckit-specify` with the composer text
   * and then plan → tasks → implement, each only after the previous run is `completed`. It stops
   * on the first run that waits for an answer, fails or is interrupted, and "Detener" cancels it.
   */
  const [pipeline, setPipeline] = useState<{ steps: string[]; next: number } | null>(null);
  const [finishing, setFinishing] = useState(false);
  const query = ai_enabled && commands && !menuClosed ? menuQuery(text, caret) : null;
  const menuItems = query !== null && commands ? filterCommands(commands, query) : [];
  const menuOpen = query !== null;
  const optionId = useCallback((i: number) => `${menuId}-opt-${i}`, [menuId]);
  const commandNames = (commands ?? []).map((c) => c.name);

  const placeCaret = (value: string, position: number) => {
    setCaret(position);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      // Never pull focus: a composer filled by a button must not swallow the keystroke or the
      // Enter that the click was meant to consume, which sent commands the user never wrote.
      if (!el || document.activeElement !== el) return;
      el.setSelectionRange(position, position);
    });
    void value;
  };

  /** Fill the composer (never sends): suggestions, chips and menu selections share it. */
  const insertCommand = (value: string) => {
    setText(value);
    setMenuClosed(true);
    setUnknown(null);
    placeCaret(value, value.length);
  };

  const selectCommand = (cmd: CommandDef) => {
    const rest = text.replace(/^\/\S*\s?/, "");
    const value = `/${cmd.name} ${rest}`;
    setText(value);
    setHint(cmd);
    setMenuClosed(true);
    placeCaret(value, cmd.name.length + 2);
  };

  const finishCommand = async () => {
    if (!session || finishing) return;
    setFinishing(true);
    setError(null);
    try {
      onSession(await api.post<AssistantSession>(`/api/assistant/sessions/${session.id}/command/finish`));
      setActiveConflict(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.assistant.failedToSend);
    } finally {
      setFinishing(false);
    }
  };

  /** The composer holds a brief for /speckit-specify: offer to run the whole pipeline. */
  const pipelineAvailable =
    ai_enabled && !sending && !busy && images.length === 0 && session?.status !== "archived"
    && text.trim().startsWith("/speckit-specify");

  const startPipeline = () => {
    const brief = text.trim();
    if (!brief) return;
    const steps = [brief, "/speckit-plan", "/speckit-tasks", "/speckit-implement"];
    setPipeline({ steps, next: 1 });
    void send(brief);
  };

  const commandName = (value: string) => value.trim().split(/\s+/)[0].replace(/^\//, "");

  useEffect(() => {
    if (!pipeline || sending || busy || !session) return;
    if (pipeline.next >= pipeline.steps.length) { setPipeline(null); return; }
    const previous = commandName(pipeline.steps[pipeline.next - 1]);
    const runs = session.command_runs ?? [];
    const last = [...runs].reverse().find((run) => run.command === previous);
    if (!last || last.status === "running") return;         // still being created: wait
    if (last.status !== "completed") {                       // it asked, failed or was stopped
      setPipeline(null);
      if (last.status !== "waiting") {
        setError(t.assistant.pipelineStopped(previous));
      }
      return;
    }
    const value = pipeline.steps[pipeline.next];
    setPipeline({ ...pipeline, next: pipeline.next + 1 });
    void send(value);
  }, [busy, sending, session, pipeline, t]);

  const runsByMessage = new Map<number, CommandRun[]>();
  for (const run of [...(session?.command_runs ?? [])].reverse()) {
    if (run.message_id === null) continue;
    runsByMessage.set(run.message_id, [...(runsByMessage.get(run.message_id) ?? []), run]);
  }

  useEffect(() => {
    onActivityChange?.(sending || busy);
  }, [sending, busy, onActivityChange]);

  const messages: AssistantMessage[] = [...(session?.messages ?? [])];
  if (pending !== null)
    messages.push({ id: -1, role: "user", content: pending, created_at: "" });

  const toolCount = (() => {
    let lastUserIndex = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastUserIndex = i;
        break;
      }
    }
    if (lastUserIndex === -1) return 0;
    let count = 0;
    for (let i = lastUserIndex + 1; i < messages.length; i++) {
      // Skip background preview outcome messages; they are not agent tool calls.
      if (
        messages[i].role === "tool" &&
        messages[i].tool_name !== "preview"
      )
        count += 1;
    }
    return count;
  })();

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, sending, busy]);

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  // The composer grows with its text up to 40% of the screen, then scrolls.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.4)}px`;
  }, [text]);

  /** Uploads the chosen files as briefs of this conversation (creating it when needed). */
  async function attach(files: FileList | null) {
    if (!files || files.length === 0) return;
    const room = maxImages - images.length;
    if (room <= 0) {
      setNotice(t.assistant.attachmentLimit.replace("{max}", String(maxImages)));
      return;
    }
    setError(null);
    setNotice(null);
    setUploading(true);
    try {
      let target = session;
      if (!target) {
        if (!createSession) return;
        target = await createSession(t.assistant.attachments);
        onSession(target);
      }
      const uploaded: Attachment[] = [];
      for (const file of Array.from(files).slice(0, room)) {
        uploaded.push(await uploadAttachment(target.id, file));
      }
      setImages((current) => [...current, ...uploaded]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.assistant.attachmentFailed);
    } finally {
      setUploading(false);
      if (filesRef.current) filesRef.current.value = "";
    }
  }

  async function removeImage(image: Attachment) {
    setImages((current) => current.filter((a) => a.id !== image.id));
    // A bound image belongs to a sent message: deleting it is the user's explicit action.
    await deleteAttachment(image.id).catch(() => undefined);
  }

  /** Removes an image that is already part of a sent message (feature 024, US4). */
  async function removeSentImage(messageId: number, image: Attachment) {
    if (!session) return;
    await deleteAttachment(image.id).catch(() => undefined);
    onSession({
      ...session,
      messages: (session.messages ?? []).map((m) =>
        m.id === messageId
          ? { ...m, attachments: (m.attachments ?? []).filter((a) => a.id !== image.id) }
          : m,
      ),
    });
  }

  /** Drag/drop and paste reuse the file picker's upload path. */
  function onDrop(event: DragEvent<HTMLElement>) {
    const files = event.dataTransfer?.files;
    if (!files || files.length === 0) return;
    event.preventDefault();
    setDragging(false);
    void attach(files);
  }

  function onPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const files = event.clipboardData?.files;
    if (!files || files.length === 0) return;      // plain text is pasted normally
    event.preventDefault();
    void attach(files);
  }

  /** The first image send asks for the notice once per account (FR-006). */
  async function acceptNotice() {
    setNoticeOpen(false);
    setNoticeAccepted(true);
    await acceptAttachmentsNotice().catch(() => undefined);
    void send(undefined, true);
  }

  async function send(override?: string, noticeClicked = false) {
    const trimmed = (override ?? text).trim();
    if ((!trimmed && images.length === 0) || sending || !ai_enabled || busy) return;
    const needsNotice = images.length > 0 && !noticeClicked && !noticeAccepted
      && !user?.attachments_notice_at;
    if (needsNotice) {
      setNoticeOpen(true);
      return;
    }
    setText("");
    setHint(null);
    setPicker(null);
    setUnknown(null);
    setActiveConflict(false);
    setPending(trimmed || t.assistant.attachments);
    setSending(true);
    setError(null);
    setNotice(null);
    const attached = images;
    try {
      let target = session;
      if (!target) {
        if (!createSession) return;
        target = await createSession(trimmed || t.assistant.attachments);
        onSession(target);
      }
      const res = await api.post<{
        messages: AssistantMessage[];
        session: AssistantSession;
      }>(`/api/assistant/sessions/${target.id}/messages`, {
        text: trimmed,
        ...(attached.length ? { attachments: attached.map((a) => a.id) } : {}),
      });
      const known = new Set((res.session.messages ?? []).map((m) => m.id));
      const next = {
        ...res.session,
        messages: [
          ...(res.session.messages ?? []),
          ...(res.messages ?? []).filter((m) => !known.has(m.id)),
        ],
      };
      onSession(next);
      setImages([]);            // the briefs now belong to the message that was sent
    } catch (e) {
      setText(trimmed);
      const details = e instanceof ApiError ? e.details ?? {} : {};
      if (isAssistantBusy(e)) {
        markBusy();
      } else if (e instanceof ApiError && e.code === "needs_spec") {
        setPicker({
          command: String(details.command ?? ""),
          specs: (details.specs as SpecChoice[] | undefined) ?? [],
          text: trimmed,
        });
      } else if (e instanceof ApiError && e.code === "unknown_command") {
        setUnknown((details.commands as string[] | undefined) ?? commandNames);
        setError(e.message);
      } else if (e instanceof ApiError && e.code === "command_active") {
        setActiveConflict(details.status === "waiting");
        setError(e.message);
      } else if (isAssistantCapacity(e)) {
        setNotice(t.assistant.capacity);
      } else {
        setError(e instanceof ApiError ? e.message : t.assistant.failedToSend);
      }
    } finally {
      setPending(null);
      setSending(false);
      textareaRef.current?.focus();
    }
  }

  // Like common AI chats: Enter sends, Shift+Enter adds a line (IME composition is left alone).
  // With the `/` menu open the keys move and pick (plan §10).
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (menuOpen && !e.nativeEvent.isComposing) {
      const n = menuItems.length;
      if (e.key === "Escape") {
        // Escape dismisses the innermost thing: the menu closes and the event does not reach the
        // shell, which closes the docked panel on Escape (feature 024 polish: the chat lives there).
        e.preventDefault();
        e.stopPropagation();
        setMenuClosed(true);
        return;
      }
      if (n > 0) {
        const moves: Record<string, number> = {
          ArrowDown: (activeIndex + 1) % n,
          ArrowUp: (activeIndex - 1 + n) % n,
          Home: 0,
          End: n - 1,
        };
        if (e.key in moves) {
          e.preventDefault();
          setActiveIndex(moves[e.key]);
          return;
        }
        if ((e.key === "Enter" && !e.shiftKey) || e.key === "Tab") {
          e.preventDefault();
          selectCommand(menuItems[Math.min(activeIndex, n - 1)]);
          return;
        }
      }
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div
          ref={transcriptRef}
          role="log"
          aria-label={t.assistant.transcriptLabel}
          aria-live="polite"
          tabIndex={0}
          className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 focus-visible:-outline-offset-4 sm:p-6"
        >
        {messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <span className="rounded-2xl bg-accent-soft p-3 text-accent">
              <Sparkles className="h-8 w-8" aria-hidden />
            </span>
            <p className="max-w-sm text-base text-ink-2">
              {t.assistant.greeting}
            </p>
          </div>
        ) : (
          messages.map((m) => {
            if (m.role === "tool") {
              const label =
                t.assistant.tools[m.tool_name ?? ""] ?? t.assistant.toolGeneric;
              const Icon = m.tool_name
                ? TOOL_ICONS[m.tool_name] ?? Wrench
                : Wrench;
              return (
                <div key={m.id} className="flex">
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-sm text-ink-2"
                    title={label}
                    data-tool={m.tool_name}
                  >
                    <Icon className="h-3.5 w-3.5" aria-hidden />
                    <span>{m.content || label}</span>
                  </span>
                </div>
              );
            }
            if (m.role === "user") {
              const runs = runsByMessage.get(m.id) ?? [];
              return (
                <div key={m.id} className="flex flex-col gap-2">
                  {m.attachments?.length ? (
                    <ul
                      aria-label={t.assistant.attachments}
                      className="flex flex-wrap justify-end gap-2"
                    >
                      {m.attachments.map((a) => (
                        <li key={a.id} className="relative">
                          <a
                            href={a.url}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={t.assistant.attachmentOpen.replace(
                              "{name}",
                              a.original_name ?? String(a.id),
                            )}
                            className="block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                          >
                            <img
                              src={a.url}
                              alt={a.original_name ?? t.assistant.attachments}
                              className="h-24 w-24 rounded-lg border border-line object-cover"
                            />
                          </a>
                          <button
                            type="button"
                            onClick={() => void removeSentImage(m.id, a)}
                            aria-label={t.assistant.attachmentRemove.replace(
                              "{name}",
                              a.original_name ?? String(a.id),
                            )}
                            // px, not rem: the 24 px minimum of WCAG 2.5.8 must not follow the type scale
                            className="absolute -right-1.5 -top-1.5 inline-flex h-[24px] w-[24px] items-center justify-center rounded-full border border-line bg-surface text-ink-2 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                          >
                            <X className="h-3 w-3" aria-hidden />
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {m.content.trim() ? (
                    <div className="flex justify-end">
                      <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-accent-soft px-3.5 py-2.5 text-base leading-relaxed text-ink">
                        {m.content}
                      </p>
                    </div>
                  ) : null}
                  {runs.map((run) => (
                    <CommandRunChip
                      key={run.id}
                      run={run}
                      finishing={finishing}
                      onFinish={() => void finishCommand()}
                      onRerun={insertCommand}
                      onOpenFile={onOpenFile}
                    />
                  ))}
                </div>
              );
            }
            if (!m.content.trim()) return null;
            const suggestions: CommandSuggestionItem[] =
              m.suggestions ?? inlineSuggestions(m.content, commandNames);
            return (
              <div key={m.id} className="flex gap-3">
                <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                  <Sparkles className="h-4 w-4" aria-hidden />
                </span>
                <div className="flex min-w-0 flex-col gap-2">
                  <ChatText text={m.content} />
                  <CommandSuggestions items={suggestions} onInsert={insertCommand} />
                </div>
              </div>
            );
          })
        )}
        {sending ? (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            {t.assistant.thinking}
          </div>
        ) : null}
          {session && !sending ? (
            <RunStatus
              session={session}
              busy={busy}
              onSession={onSession}
              release={release}
            />
          ) : null}
        </div>

        {mapOverlay}
      </div>

      {notice ? (
        <div className="px-3 sm:px-4">
          <Alert tone="warning">{notice}</Alert>
        </div>
      ) : null}

      {noticeOpen ? (
        <div className="flex flex-col gap-2 px-3 pt-2 sm:px-4">
          <Alert tone="warning">{t.assistant.attachmentNotice}</Alert>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void acceptNotice()}
              className="inline-flex min-h-tap items-center rounded-lg bg-primary px-3 text-sm text-on-primary hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              {t.assistant.attachmentNoticeAccept}
            </button>
            <button
              type="button"
              onClick={() => setNoticeOpen(false)}
              className="inline-flex min-h-tap items-center rounded-lg border border-line px-3 text-sm text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              {t.common.cancel}
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="px-3 sm:px-4">
          <Alert tone="error">{error}</Alert>
        </div>
      ) : null}

      {unknown && unknown.length > 0 ? (
        <div className="flex flex-col gap-2 px-3 pt-2 sm:px-4">
          <p className="text-sm text-ink-2">{t.assistant.commands.unknownCommand}</p>
          <CommandSuggestions
            items={unknown.map((command) => ({ command, arguments: "" }))}
            onInsert={insertCommand}
          />
        </div>
      ) : null}

      {activeConflict ? (
        <div className="px-3 pt-2 sm:px-4">
          <button
            type="button"
            onClick={() => void finishCommand()}
            disabled={finishing}
            className="inline-flex min-h-tap items-center rounded-lg border border-line px-3 text-sm text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
          >
            {t.assistant.commands.finish}
          </button>
        </div>
      ) : null}

      {pipeline ? (
        <div className="flex flex-wrap items-center gap-2 px-3 pt-2 sm:px-4">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 text-xs text-accent">
            <ListChecks className="h-3.5 w-3.5" aria-hidden />
            {t.assistant.pipelineStep(Math.min(pipeline.next, pipeline.steps.length - 1),
                                      pipeline.steps.length - 1)}
          </span>
          <button
            type="button"
            onClick={() => setPipeline(null)}
            className="inline-flex min-h-tap items-center gap-1.5 rounded-lg border border-line px-2.5 text-xs text-ink hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <Square className="h-3 w-3" aria-hidden />
            {t.assistant.stop}
          </button>
        </div>
      ) : null}

      {picker && session ? (
        <div className="px-3 pt-2 sm:px-4">
          <SpecPicker
            command={picker.command}
            specs={picker.specs}
            busy={sending}
            onCancel={() => setPicker(null)}
            onPick={async (folder) => {
              const pending = picker.text;
              setPicker(null);
              try {
                onSession(
                  await api.patch<AssistantSession>(`/api/assistant/sessions/${session.id}`, {
                    current_spec: folder,
                  }),
                );
                await send(pending);
              } catch (err) {
                setError(err instanceof ApiError ? err.message : t.assistant.failedToSend);
              }
            }}
          />
        </div>
      ) : null}

      {session ? (
        <div className="px-3 sm:px-4">
          <BudgetNotice session={session} />
        </div>
      ) : null}

      {session?.status === "archived" ? (
        <div className="border-t border-line p-3 text-sm text-ink-muted">
          {t.assistant.statusArchived}
        </div>
      ) : (
        <div
          className="p-3 sm:p-4"
          data-drop-target=""
          onDragOver={(e) => {
            if (e.dataTransfer?.types?.includes("Files")) {
              e.preventDefault();
              setDragging(true);
            }
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          {session?.status === "applied" ? (
            <p className="mb-2 text-sm text-ink-muted">
              {t.assistant.appliedHint}
            </p>
          ) : null}
          <label htmlFor={composerId} className="sr-only">
            {t.assistant.composerLabel}
          </label>
          {dragging ? (
            <p className="mb-2 rounded-lg border border-dashed border-line-strong px-3 py-2 text-sm text-ink-2">
              {t.assistant.attachmentDrop}
            </p>
          ) : null}
          {menuOpen ? (
            <div className="mb-2">
              <CommandMenu
                id={menuId}
                items={menuItems}
                activeIndex={Math.min(activeIndex, Math.max(menuItems.length - 1, 0))}
                hasSpec={!!session?.current_spec}
                optionId={optionId}
                onSelect={selectCommand}
                onActiveChange={setActiveIndex}
              />
            </div>
          ) : null}
          <div
            className={`rounded-2xl border border-line bg-surface shadow-sm focus-within:ring-2 focus-within:ring-field-focus ${
              !ai_enabled || busy ? "opacity-60" : ""
            }`}
          >
            {images.length > 0 ? (
              <ul
                aria-label={t.assistant.attachments}
                className="flex flex-wrap gap-2 px-3 pt-3"
              >
                {images.map((a) => (
                  <li key={a.id} className="relative">
                    <img
                      src={a.url}
                      alt={a.original_name ?? t.assistant.attachments}
                      className="h-16 w-16 rounded-lg border border-line object-cover"
                    />
                    <button
                      type="button"
                      onClick={() => void removeImage(a)}
                      aria-label={t.assistant.attachmentRemove.replace(
                        "{name}",
                        a.original_name ?? String(a.id),
                      )}
                      // px, not rem: the 24 px minimum of WCAG 2.5.8 must not follow the type scale
                            className="absolute -right-1.5 -top-1.5 inline-flex h-[24px] w-[24px] items-center justify-center rounded-full border border-line bg-surface text-ink-2 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                    >
                      <X className="h-3 w-3" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <textarea
              id={composerId}
              ref={textareaRef}
              rows={2}
              maxLength={8000}
              disabled={!ai_enabled || busy}
              value={text}              role="combobox"
              aria-autocomplete="list"
              aria-expanded={menuOpen}
              aria-controls={menuOpen ? menuId : undefined}
              aria-activedescendant={
                menuOpen && menuItems.length > 0
                  ? optionId(Math.min(activeIndex, menuItems.length - 1))
                  : undefined
              }
              onChange={(e) => {
                setText(e.target.value);
                setCaret(e.target.selectionStart ?? e.target.value.length);
                setActiveIndex(0);
                setMenuClosed(false);
              }}
              onSelect={(e) => setCaret(e.currentTarget.selectionStart ?? 0)}
              onBlur={() => setMenuClosed(true)}
              onFocus={() => setMenuClosed(false)}
              onKeyDown={onKeyDown}
              onPaste={onPaste}
              placeholder={t.assistant.composerPlaceholder}
              className="block max-h-[40vh] min-h-[3.5rem] w-full resize-none overflow-y-auto border-0 bg-transparent px-4 pt-3 text-base leading-relaxed text-ink placeholder:text-ink-muted focus:outline-none focus:ring-0"
            />
            <div className="flex items-center justify-between gap-3 px-3 pb-3 pt-1">
              <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
                <button
                  type="button"
                  data-attach=""
                  onClick={() => filesRef.current?.click()}
                  disabled={!ai_enabled || busy || sending || uploading || vision_enabled === false}
                  aria-label={t.assistant.attach}
                  title={
                    vision_enabled === false
                      ? t.assistant.attachmentVisionOff
                      : t.assistant.attachHint.replace("{mb}", String(attachments_max_mb ?? 5))
                  }
                  className="inline-flex min-h-tap min-w-tap items-center justify-center rounded-xl border border-line bg-surface text-ink-2 hover:border-line-strong hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  ) : (
                    <Paperclip className="h-4 w-4" aria-hidden />
                  )}
                  <span className="sr-only">
                    {uploading ? t.assistant.attachmentUploading : t.assistant.attach}
                  </span>
                </button>
                <input
                  ref={filesRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif"
                  multiple
                  className="hidden"
                  tabIndex={-1}
                  aria-hidden
                  onChange={(e) => void attach(e.target.files)}
                />
                {session && onToggleMap ? (
                  <button
                    type="button"
                    data-agent-map-pill=""
                    aria-pressed={!!mapOpen}
                    aria-label={t.assistant.agentMap.pill.replace(
                      "{tools}",
                      t.assistant.agentMap.toolsCount(toolCount),
                    )}
                    title={t.assistant.agentMap.open}
                    onClick={(e) => onToggleMap(e.currentTarget)}
                    className={`inline-flex min-h-tap items-center gap-1.5 rounded-full border px-2.5 text-xs text-ink-2 hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
                      mapOpen
                        ? "border-line-strong bg-subtle"
                        : "border-line bg-surface"
                    }`}
                  >
                    <span className="relative inline-flex h-2 w-2 shrink-0">
                      {sending || busy ? (
                        <span
                          className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-75 motion-safe:animate-ping"
                          aria-hidden
                        />
                      ) : null}
                      <span
                        className={`relative inline-flex h-2 w-2 rounded-full ${
                          sending || busy ? "bg-accent" : "bg-success"
                        }`}
                      />
                    </span>
                    <span>{t.assistant.agentMap.toolsCount(toolCount)}</span>
                  </button>
                ) : null}
                <span>{t.assistant.enterHint}</span>
                {text.length > 7000 ? (
                  <span>
                    {t.assistant.charsCounter.replace(
                      "{n}",
                      String(text.length),
                    )}{" "}
                    / 8000
                  </span>
                ) : null}
              </div>
              {pipelineAvailable && (
                <button
                  type="button"
                  onClick={startPipeline}
                  title={t.assistant.pipelineHint}
                  className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full border border-accent-line bg-accent-soft px-3 text-sm text-accent hover:bg-accent-soft/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                  <ListChecks className="h-4 w-4" aria-hidden />
                  {t.assistant.pipeline}
                </button>
              )}
              <button
                type="button"
                onClick={() => void send()}
                disabled={
                  !ai_enabled || sending || busy || (!text.trim() && images.length === 0)
                }
                className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:bg-primary/50"
              >
                {sending ? (
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                ) : (
                  <ArrowUp className="h-5 w-5" aria-hidden />
                )}
                <span className="sr-only">{t.assistant.send}</span>
              </button>
            </div>
          </div>
          {hint && hint.argument_hint && text.startsWith(`/${hint.name}`) ? (
            <p className="mt-2 text-sm text-ink-muted">
              {t.assistant.commands.argumentHint.replace("{hint}", hint.argument_hint)}
            </p>
          ) : null}
          {variant === "page" ? (
            <p className="mt-2 text-center text-sm text-ink-muted">
              {t.assistant.privacyNote}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
