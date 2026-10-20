import { useEffect, useRef, useState } from "react";
import { Zap } from "lucide-react";
import { ApiError, askReauth } from "../../api/client";
import { projectsApi } from "../../api/projects";
import type { AssistantSession, RunContract } from "../../api/types";
import { useT } from "../../i18n";
import { Alert } from "../Alert";
import { Button } from "../Button";

/**
 * Feature 028, simplified on the owner's request: authorising an Auto run is one line, not a form.
 *
 * The contract keeps its shape (and its step-up) but everything is the documented default: the
 * whole pipeline up to apply, every configured source, the installation's limits, no modification
 * of existing artifacts, automatic rollback, no extra visibility. The super user only types the
 * password (plus the two-step code on `internet`).
 */
export function RunContractDialog({
  session,
  goal,
  onClose,
  onConfirmed,
}: {
  session: AssistantSession;
  goal: string;
  onClose: () => void;
  onConfirmed: (session: AssistantSession) => void;
}) {
  const t = useT();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    panelRef.current?.querySelector("input")?.focus();
  }, []);

  useEffect(() => {
    const node = panelRef.current;
    if (!node) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    node.addEventListener("keydown", onKey);
    return () => node.removeEventListener("keydown", onKey);
  }, [onClose]);

  const contract = (): RunContract => ({
    goal: goal.trim() || t.assistant.modes.auto,
    stages: ["draft", "preview", "apply"],
  });

  const authorize = async () => {
    setSaving(true);
    setError(null);
    try {
      const result = await projectsApi.confirmContract(session.id, {
        contract: contract(),
        password,
        code: code.trim() || null,
      });
      onConfirmed(result.session);
    } catch (err) {
      if (err instanceof ApiError && err.code === "reauth_required" && (await askReauth())) {
        setSaving(false);
        return void (await authorize());
      }
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      aria-labelledby="auto-confirm-title"
      data-run-contract=""
      className="mb-2 rounded-xl border border-accent/40 bg-accent-soft/40 p-3 focus:outline-none"
    >
      <h2 id="auto-confirm-title" className="flex items-center gap-1.5 text-sm font-semibold text-ink">
        <Zap className="h-4 w-4 text-accent" aria-hidden />
        {t.assistant.contract.title}
      </h2>
      <p className="mt-1 text-xs text-ink-2">{t.assistant.contract.defaults}</p>

      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-xs text-ink-muted">{t.assistant.contract.password}</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && password) void authorize();
            }}
            className="min-h-tap w-full rounded-lg border border-line bg-surface px-3 text-ink"
          />
        </label>
        <label className="flex w-28 flex-col gap-1">
          <span className="text-xs text-ink-muted">{t.assistant.contract.code}</span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={8}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            className="min-h-tap w-full rounded-lg border border-line bg-surface px-3 text-ink"
          />
        </label>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <div className="mt-2 flex flex-wrap justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          {t.assistant.contract.cancel}
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => void authorize()}
          disabled={saving || !password}
          data-contract-confirm=""
        >
          {saving ? t.assistant.contract.confirming : t.assistant.contract.confirm}
        </Button>
      </div>
    </section>
  );
}
