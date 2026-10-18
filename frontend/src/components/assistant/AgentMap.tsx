import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { X } from "lucide-react";
import { api, ApiError } from "../../api/client";
import { t, useT } from "../../i18n";
import { dateTimeFormat } from "../../lib/intl";
import { Alert } from "../Alert";
import { Spinner } from "../Spinner";
import type {
  AssistantActivity,
  AssistantActivityRound,
  AssistantActivityTool,
  AssistantRunStatus,
  AssistantRunSummary,
} from "../../api/types";

export const ACTIVITY_POLL_MS = 2000;

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60000) {
    const seconds = (ms / 1000).toFixed(1).replace(".", ",");
    return `${seconds} s`;
  }
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes} min ${seconds} s`;
}

export function formatTokens(n: number): string {
  const whole = Math.max(0, Math.floor(n));
  if (whole < 1000) return String(whole);
  return String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function runElapsedMs(
  run: { started_at: string; finished_at: string | null },
  now: number,
): number | null {
  const started = new Date(run.started_at).getTime();
  if (Number.isNaN(started)) return null;
  const finished = run.finished_at ? new Date(run.finished_at).getTime() : now;
  if (Number.isNaN(finished)) return null;
  if (finished < started) return null;
  return finished - started;
}

const STATUS_DOT: Record<AssistantRunStatus | "none", string> = {
  running: "bg-accent",
  done: "bg-success",
  ready: "bg-success",
  stopped: "bg-warning",
  budget: "bg-warning",
  limit: "bg-warning",
  error: "bg-danger",
  none: "bg-line-strong",
};

interface AgentStatusDotProps {
  status: AssistantRunStatus | "none";
  pulse?: boolean;
}

function AgentStatusDot({ status, pulse }: AgentStatusDotProps) {
  return (
    <span className="relative inline-flex h-2 w-2 shrink-0">
      {pulse ? (
        <span
          className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-75 motion-safe:animate-ping"
          aria-hidden
        />
      ) : null}
      <span
        className={`relative inline-flex h-2 w-2 rounded-full ${STATUS_DOT[status]}`}
      />
    </span>
  );
}

interface UseAgentActivityState {
  activity: AssistantActivity | null;
  error: boolean;
  loading: boolean;
}

export function useAgentActivity(
  sessionId: number,
  externalBusy?: boolean,
): UseAgentActivityState {
  const [activity, setActivity] = useState<AssistantActivity | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [gone, setGone] = useState(false);

  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const sessionRef = useRef(sessionId);
  const prevExternalRef = useRef(Boolean(externalBusy));

  useEffect(() => {
    sessionRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(
    async (cancelled: () => boolean) => {
      const idAtStart = sessionRef.current;
      if (inFlightRef.current || cancelled()) return;
      inFlightRef.current = true;
      try {
        const data = await api.get<AssistantActivity>(
          `/api/assistant/sessions/${idAtStart}/activity`,
        );
        if (cancelled() || idAtStart !== sessionRef.current || !mountedRef.current) {
          return;
        }
        setActivity(data);
        setError(false);
      } catch (err) {
        if (cancelled() || !mountedRef.current) return;
        if (err instanceof ApiError && err.status === 404) {
          setGone(true);
          setError(true);
        } else {
          setError(true);
        }
      } finally {
        if (mountedRef.current) {
          inFlightRef.current = false;
          setLoading(false);
        } else {
          inFlightRef.current = false;
        }
      }
    },
    [sessionId],
  );

  // Effect A: reset state and fetch once immediately when sessionId changes.
  useEffect(() => {
    let cancelled = false;
    setActivity(null);
    setError(false);
    setLoading(true);
    setGone(false);
    inFlightRef.current = false;

    void load(() => cancelled);

    return () => {
      cancelled = true;
    };
  }, [sessionId, load]);

  const live = !gone && (Boolean(externalBusy) || Boolean(activity?.busy));

  // Effect B: polling chain, only while live.
  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      if (cancelled) return;
      await load(() => cancelled);
      if (cancelled) return;
      const stillLive =
        !gone && (Boolean(externalBusy) || Boolean(activity?.busy));
      if (!stillLive) return;
      timer = setTimeout(tick, ACTIVITY_POLL_MS);
    };

    timer = setTimeout(() => void tick(), ACTIVITY_POLL_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [live, load, externalBusy, gone, activity?.busy]);

  // Effect C: when externalBusy goes true -> false, final fetch so finished run shows.
  useEffect(() => {
    const prev = prevExternalRef.current;
    prevExternalRef.current = Boolean(externalBusy);

    if (prev && !externalBusy && !gone) {
      let cancelled = false;
      void load(() => cancelled);
      return () => {
        cancelled = true;
      };
    }
  }, [externalBusy, gone, load]);

  return { activity, error, loading };
}

export function useAgentMapToggle(): {
  open: boolean;
  toggle: (opener?: HTMLElement | null) => void;
  close: (restoreFocus?: boolean) => void;
} {
  const [open, setOpen] = useState(false);
  const openRef = useRef(false);
  const openerRef = useRef<HTMLElement | null>(null);

  openRef.current = open;

  const close = useCallback((restoreFocus: boolean = true) => {
    setOpen(false);
    if (restoreFocus) {
      const opener = openerRef.current;
      if (opener && opener.isConnected) {
        opener.focus();
      }
    }
  }, []);

  const toggle = useCallback(
    (opener?: HTMLElement | null) => {
      const isOpen = openRef.current;
      if (isOpen) {
        close(false);
        return;
      }
      openerRef.current =
        opener ?? (document.activeElement as HTMLElement | null);
      setOpen(true);
    },
    [close],
  );

  return { open, toggle, close };
}

function statusText(status: AssistantRunStatus): string {
  return (
    (t.assistant.agentMap.status as Record<string, string>)[status] ?? status
  );
}

interface ToolNodeProps {
  tool: AssistantActivityTool;
  round: number;
  index: number;
  expanded: boolean;
  onToggle: (key: string) => void;
}

function ToolNode({ tool, round, index, expanded, onToggle }: ToolNodeProps) {
  const t = useT();
  const key = `${round}-${index}`;
  const label = tool.label || tool.name;
  const roundLabel = t.assistant.agentMap.roundLower.replace(
    "{n}",
    String(round),
  );
  const statusLabel =
    tool.status === "ok"
      ? t.assistant.agentMap.toolOk
      : tool.status === "error"
        ? t.assistant.agentMap.toolError
        : t.assistant.agentMap.toolRunning;

  return (
    <li className="relative">
      <span
        aria-hidden
        className="absolute -left-4 top-5 w-4 border-t border-line"
      />
      <button
        type="button"
        data-tool-node=""
        data-tool-status={tool.status}
        aria-expanded={expanded}
        onClick={() => onToggle(key)}
        className="flex w-full min-h-tap flex-col items-start rounded-xl border border-line bg-surface px-3 py-2 text-left hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        <span className="flex w-full items-center gap-2">
          <span className="relative inline-flex h-2 w-2 shrink-0">
            {tool.status === "running" ? (
              <span
                className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-75 motion-safe:animate-ping"
                aria-hidden
              />
            ) : null}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                tool.status === "ok"
                  ? "bg-success"
                  : tool.status === "error"
                    ? "bg-danger"
                    : "bg-accent"
              }`}
            />
          </span>
          <span className="sr-only">{statusLabel}</span>
          <span
            className="min-w-0 flex-1 truncate text-sm font-medium text-ink"
            title={label}
          >
            {label}
          </span>
        </span>
        <span className="text-xs tabular-nums text-ink-muted">
          {formatDuration(tool.ms)} · {roundLabel}
        </span>
      </button>
      {expanded ? (
        <dl
          data-tool-details=""
          className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-xl bg-subtle px-3 py-2 text-xs"
        >
          <dt className="text-ink-muted">{t.assistant.agentMap.detailTool}</dt>
          <dd className="min-w-0 break-words text-ink-2">
            <code>{tool.name}</code>
          </dd>
          <dt className="text-ink-muted">{t.assistant.agentMap.detailStatus}</dt>
          <dd className="min-w-0 break-words text-ink-2">{statusLabel}</dd>
          <dt className="text-ink-muted">{t.assistant.agentMap.detailStarted}</dt>
          <dd className="min-w-0 break-words text-ink-2">
            {(() => {
              const date = new Date(tool.started_at);
              return Number.isNaN(date.getTime())
                ? "—"
                : dateTimeFormat({ hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
            })()}
          </dd>
          <dt className="text-ink-muted">{t.assistant.agentMap.detailDuration}</dt>
          <dd className="min-w-0 break-words text-ink-2">
            {formatDuration(tool.ms)}
          </dd>
        </dl>
      ) : null}
    </li>
  );
}

interface RunRowProps {
  run: AssistantRunSummary;
  now: number;
}

function RunRow({ run, now }: RunRowProps) {
  const t = useT();
  const elapsed = runElapsedMs(run, now);
  return (
    <li className="flex items-center gap-2 rounded-xl border border-line bg-surface p-2">
      <AgentStatusDot status={run.status} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="min-w-0 truncate text-sm font-medium text-ink">
            {t.assistant.agentMap.runLabel.replace("{id}", String(run.id))}
          </span>
          <span className="shrink-0 text-xs text-ink-muted">
            {statusText(run.status)}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-ink-muted">
          {t.assistant.agentMap.rounds.replace("{n}", String(run.rounds))} ·{" "}
          {formatDuration(elapsed)} · {formatTokens(run.tokens)}{" "}
          {t.assistant.agentMap.tokensLower}
        </p>
      </div>
    </li>
  );
}

interface AgentMapOverlayProps {
  sessionId: number;
  title: string;
  busy?: boolean;
  onClose: () => void;
  placement?: "chat" | "page";
}

export function AgentMapOverlay({
  sessionId,
  title,
  busy,
  onClose,
  placement = "chat",
}: AgentMapOverlayProps) {
  const t = useT();
  const { activity, error, loading } = useAgentActivity(sessionId, busy);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(
    () => new Set(),
  );
  const [now, setNow] = useState(() => Date.now());

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const run = activity?.run ?? null;
  const rounds = useMemo<AssistantActivityRound[]>(
    () => activity?.rounds ?? [],
    [activity],
  );
  const tools = useMemo(() => {
    const flattened: {
      tool: AssistantActivityTool;
      round: number;
      index: number;
    }[] = [];
    for (const round of rounds) {
      round.tools.forEach((tool, index) => {
        flattened.push({ tool, round: round.n, index });
      });
    }
    return flattened;
  }, [rounds]);

  const toolCount = tools.length;

  const elapsed = useMemo(() => {
    if (!run) return null;
    return runElapsedMs(run, now);
  }, [run, now]);

  const isRunning = run?.status === "running";

  useEffect(() => {
    if (!isRunning) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [isRunning]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) {
        event.preventDefault();
        onCloseRef.current();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const toggleTool = useCallback((key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const runsToShow = useMemo(() => {
    if (!activity) return [];
    const reversed = [...activity.runs].reverse();
    if (activity.run) {
      return reversed.filter((r) => r.id !== activity.run!.id);
    }
    return reversed;
  }, [activity]);

  const maxHeightClass =
    placement === "chat" ? "max-h-[calc(100%-1rem)]" : "max-h-[70vh]";

  return (
    <section
      role="region"
      aria-label={t.assistant.agentMap.title}
      data-agent-map=""
      className={`absolute inset-x-2 top-2 z-20 mx-auto flex max-w-[760px] flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-raised ${maxHeightClass}`}
    >
      <div className="flex items-start gap-2 border-b border-line py-2 pl-4 pr-1">
        <div className="min-w-0 flex-1 py-1">
          <h2 className="text-base font-semibold text-ink">
            {t.assistant.agentMap.title}
          </h2>
          <p
            data-agent-map-subtitle=""
            className="text-xs text-ink-muted"
          >
            {t.assistant.agentMap.subtitle(toolCount)}
          </p>
        </div>
        <button
          type="button"
          data-agent-map-close=""
          onClick={onClose}
          aria-label={t.assistant.agentMap.close}
          title={t.assistant.agentMap.close}
          className="inline-flex min-h-tap min-w-tap shrink-0 items-center justify-center rounded-xl text-ink-muted hover:bg-subtle hover:text-ink"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
      </div>

      <div
        className="min-h-0 flex-1 overflow-y-auto p-4"
        tabIndex={0}
        aria-label={t.assistant.agentMap.mapLabel}
      >
        {loading && !activity ? (
          <div
            role="status"
            className="flex items-center gap-2 text-sm text-ink-muted"
          >
            <Spinner />
            {t.assistant.agentMap.loading}
          </div>
        ) : error && !activity ? (
          <Alert tone="error">{t.assistant.agentMap.failed}</Alert>
        ) : (
          <>
            <div
              data-agent-tree=""
              className="flex flex-col sm:flex-row sm:items-start"
            >
              <div
                data-agent-node=""
                className="min-w-0 rounded-xl border border-line bg-canvas p-3 sm:w-56 sm:shrink-0"
              >
                <div className="flex items-center gap-2">
                  <AgentStatusDot
                    status={run?.status ?? "none"}
                    pulse={run?.status === "running"}
                  />
                  <p
                    className="min-w-0 truncate text-sm font-semibold text-ink"
                    title={title}
                  >
                    {title}
                  </p>
                </div>
                <p
                  className="mt-1 truncate text-xs text-ink-muted"
                  title={activity?.model ?? ""}
                >
                  {activity?.model ?? "—"} · {formatTokens(run?.tokens ?? 0)}{" "}
                  {t.assistant.agentMap.tokensLower}
                </p>
                <p aria-live="polite" className="mt-1 text-xs text-ink-2">
                  {run
                    ? `${statusText(run.status)} · ${formatDuration(elapsed)}`
                    : t.assistant.agentMap.idle}
                </p>
                {run?.current ? (
                  <p className="mt-1 truncate text-xs text-accent">
                    {t.assistant.agentMap.now.replace(
                      "{label}",
                      run.current.label,
                    )}
                  </p>
                ) : null}
              </div>

              <span
                aria-hidden
                className="hidden w-4 shrink-0 border-t border-line sm:mt-6 sm:block"
              />

              <ul
                aria-label={t.assistant.agentMap.toolsLabel}
                className="ml-3 min-w-0 flex-1 space-y-2 border-l border-line pl-4 pt-3 sm:ml-0 sm:pt-0"
              >
                {tools.length > 0 ? (
                  tools.map(({ tool, round, index }) => (
                    <ToolNode
                      key={`${round}-${index}`}
                      tool={tool}
                      round={round}
                      index={index}
                      expanded={expandedKeys.has(`${round}-${index}`)}
                      onToggle={toggleTool}
                    />
                  ))
                ) : (
                  <li className="text-sm text-ink-muted">
                    {t.assistant.agentMap.noTools}
                  </li>
                )}
              </ul>
            </div>

            <section
              aria-label={t.assistant.agentMap.background}
              className="mt-4 border-t border-line pt-3"
            >
              <h3 className="mb-2 text-sm font-semibold text-ink">
                {t.assistant.agentMap.backgroundCount(
                  activity?.background.length ?? 0,
                )}
              </h3>
              {!activity || activity.background.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  {t.assistant.agentMap.noBackground}
                </p>
              ) : (
                <ul className="ml-3 space-y-2 border-l border-line pl-4">
                  {activity.background.map((bg, index) => (
                    <li
                      key={`${bg.kind}-${index}`}
                      data-background-node=""
                      className="relative flex min-w-0 items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2"
                    >
                      <span
                        aria-hidden
                        className="absolute -left-4 top-1/2 w-4 border-t border-line"
                      />
                      <span className="relative inline-flex h-2 w-2 shrink-0">
                        {bg.status === "running" ? (
                          <span
                            className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-75 motion-safe:animate-ping"
                            aria-hidden
                          />
                        ) : null}
                        <span
                          className={`relative inline-flex h-2 w-2 rounded-full ${
                            bg.status === "running"
                              ? "bg-accent"
                              : "bg-line-strong"
                          }`}
                        />
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm text-ink-2">
                        {t.assistant.agentMap.previewTask}
                      </span>
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
                          bg.status === "running"
                            ? "bg-accent-soft text-accent-strong"
                            : "bg-subtle text-ink-muted"
                        }`}
                      >
                        {bg.status === "running"
                          ? t.assistant.agentMap.bgRunning
                          : t.assistant.agentMap.bgPending}
                      </span>
                      <span className="shrink-0 text-xs text-ink-muted">
                        {(() => {
                          const date = new Date(bg.since);
                          return Number.isNaN(date.getTime())
                            ? "—"
                            : dateTimeFormat({ hour: "2-digit", minute: "2-digit" }).format(date);
                        })()}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <details
              data-agent-runs=""
              className="mt-4 border-t border-line pt-3"
            >
              <summary className="flex min-h-tap cursor-pointer items-center text-sm font-semibold text-ink">
                {t.assistant.agentMap.runs} ({runsToShow.length})
              </summary>
              {runsToShow.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  {t.assistant.agentMap.noRuns}
                </p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {runsToShow.map((runSummary) => (
                    <RunRow key={runSummary.id} run={runSummary} now={now} />
                  ))}
                </ul>
              )}
            </details>
          </>
        )}
      </div>
    </section>
  );
}
