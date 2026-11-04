import { AlertTriangle, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { sourcesApi } from "../api/sources";
import type { ChatAnswer, ChatTurn } from "../api/types";
import { useBranding } from "../config/BrandingContext";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { useT } from "../i18n";

interface Shown extends ChatTurn {
  unknown?: ChatAnswer["unknown"];
  /** The provider's own line, when the answer could not be produced. */
  error?: { code: string; message: string; action: string | null };
}

/**
 * Feature 052 (US2): the read-only structure chat, in a non-modal panel beside the structure.
 *
 * It shows what the API returns and nothing else: a refusal (product code, before the provider is
 * called), a typed provider error with the link to Administración → IA, or an answer whose objects
 * the API already validated — the ones that are not in the structure arrive in `unknown` and are
 * chipped here so a hallucinated name never reaches a spec.
 */
export function StructureChat({ sourceName }: { sourceName: string }) {
  const t = useT();
  const T = t.sourceChat;
  const branding = useBranding();
  const [turns, setTurns] = useState<Shown[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [usage, setUsage] = useState<{ cap: number; spent_today: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement | null>(null);

  const load = useCallback(async () => {
    try {
      const history = await sourcesApi.chat(sourceName);
      setTurns(history.turns.filter((turn) => turn.text));
      setUsage({ cap: history.cap, spent_today: history.spent_today });
    } catch {
      /* the panel shows what it has; the structure above already reports a failure */
    }
  }, [sourceName]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [turns.length]);

  const ask = async () => {
    const text = question.trim();
    if (!text) return;
    setAsking(true);
    setError(null);
    setTurns((prev) => [...prev, { role: "question", text, at: new Date().toISOString() }]);
    setQuestion("");
    try {
      const answer = await sourcesApi.ask(sourceName, text);
      setTurns((prev) => [...prev, {
        role: "answer", text: answer.answer, at: answer.created_at, unknown: answer.unknown,
      }]);
      setUsage(answer.usage);
    } catch (err) {
      if (err instanceof ApiError) {
        setTurns((prev) => [...prev, {
          role: "answer", text: "", at: new Date().toISOString(),
          error: { code: err.code, message: err.message, action: aiAction(err) },
        }]);
      } else {
        setError(t.common.unexpected);
      }
    } finally {
      setAsking(false);
    }
  };

  return (
    <Card className="flex min-h-0 flex-col space-y-3 p-4 sm:p-5" aria-live="polite">
      <div>
        <h2 className="text-lg font-semibold text-ink">{T.title}</h2>
        <p className="text-sm text-ink-soft">{T.subtitle}</p>
      </div>

      {!branding.ai_enabled ? (
        <Alert tone="info"
               action={<a className="font-semibold text-accent underline" href="/admin/ia">{T.offLink}</a>}>
          {T.off}
        </Alert>
      ) : null}

      {turns.length === 0 ? <p className="text-sm text-ink-soft">{T.empty}</p> : null}
      <ol className="min-h-0 flex-1 space-y-2 overflow-y-auto lg:max-h-[calc(100dvh-26rem)]">
        {turns.map((turn, index) => (
          <li key={`${turn.at}-${index}`}
              className={turn.role === "question"
                ? "ml-6 rounded-card bg-accent-soft p-3 text-sm text-ink"
                : "mr-6 rounded-card border border-line p-3 text-sm text-ink"}>
            {turn.error ? (
              <div className="space-y-1">
                <p className="font-semibold text-danger">{turn.error.message}</p>
                <p className="text-xs text-ink-muted">{turn.error.code}</p>
                {turn.error.action === "admin_ai" ? (
                  <a className="text-sm font-semibold text-accent underline" href="/admin/ia">
                    {t.ai.action.admin_ai}
                  </a>
                ) : null}
              </div>
            ) : (
              <p className="whitespace-pre-wrap break-words">{turn.text}</p>
            )}
            {turn.unknown?.length ? (
              <div className="mt-2 rounded-lg bg-warning-soft p-2">
                <p className="flex items-center text-xs font-semibold text-warning">
                  <AlertTriangle className="mr-1 h-3.5 w-3.5" aria-hidden />{T.unknownHelp}
                </p>
                <p className="mt-1 flex flex-wrap gap-1.5">
                  {turn.unknown.map((item) => (
                    <span key={item.name}
                          className="rounded-full bg-surface px-2 py-0.5 text-xs font-medium text-warning">
                      {item.name}
                    </span>
                  ))}
                </p>
              </div>
            ) : null}
          </li>
        ))}
        <div ref={end} />
      </ol>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <div className="space-y-2">
        <label className="block text-sm font-semibold text-ink-2" htmlFor="structure-chat-question">
          {T.title}
        </label>
        <textarea
          id="structure-chat-question"
          value={question}
          rows={3}
          maxLength={2000}
          placeholder={T.placeholder}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void ask();
          }}
          className="w-full rounded-field border border-line-strong bg-surface px-3 py-2 text-ink"
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button icon={<Send className="h-4 w-4" aria-hidden />} loading={asking}
                  disabled={!question.trim() || !branding.ai_enabled} onClick={() => void ask()}>
            {asking ? T.asking : T.ask}
          </Button>
          <Button variant="ghost" icon={<Trash2 className="h-4 w-4" aria-hidden />}
                  onClick={async () => {
                    try {
                      await sourcesApi.clearChat(sourceName);
                    } catch {
                      /* nothing to report: the list below is still what the server has */
                    }
                    await load();
                  }}>
            {T.clear}
          </Button>
          {usage ? (
            <span className="text-xs text-ink-muted">{T.budget(usage.spent_today, usage.cap)}</span>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

/** The action the typed error offers: only the ones the product already knows. */
function aiAction(err: ApiError): string | null {
  const ai = (err.details.ai ?? {}) as { action?: string | null };
  if (err.code === "ai_not_configured") return "admin_ai";
  return ai.action ?? null;
}
