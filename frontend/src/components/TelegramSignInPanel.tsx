import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { TelegramStart, TelegramStatus, User } from "../api/types";
import { t, useT } from "../i18n";
import { startPolling } from "../lib/telegramPoll";
import { Alert } from "./Alert";
import { Button } from "./Button";
import { Spinner } from "./Spinner";

interface Props {
  onSignedIn: (u: User) => void;
  /** `enrollmentRequired`: the profile demands a second factor this account has not enrolled. */
  onMfa: (enrollmentRequired?: boolean) => void;
  onCancel: () => void;
}

function remaining(expiresAt: string): string {
  const s = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000));
  return t.telegram.countdown(Math.floor(s / 60), String(s % 60).padStart(2, "0"));
}

/** Sign in with Telegram (feature 007): match code, deep link (QR on wider screens), polling. */
export function TelegramSignInPanel({ onSignedIn, onMfa, onCancel }: Props) {
  const t = useT();
  const [data, setData] = useState<TelegramStart | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [countdown, setCountdown] = useState("");
  // Parent callbacks change identity on every render; keep the latest without restarting polling.
  const handlers = useRef({ onSignedIn, onMfa });
  handlers.current = { onSignedIn, onMfa };

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setData(null);
    api
      .post<TelegramStart>("/api/auth/telegram/start")
      .then((value) => !cancelled && setData(value))
      .catch((e) => {
        if (cancelled) return;
        const known = e instanceof ApiError && [401, 423, 429].includes(e.status);
        setError(known ? e.message : t.telegram.unavailable);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  useEffect(() => {
    if (!data) return;
    setCountdown(remaining(data.expires_at));
    const tickTimer = setInterval(() => setCountdown(remaining(data.expires_at)), 1000);
    const stop = startPolling<TelegramStatus>({
      fetch: () => api.get<TelegramStatus>("/api/auth/telegram/status"),
      isFinal: (v) => v.status !== "pending",
      onValue: (v) => {
        if (v.status === "signed_in") handlers.current.onSignedIn(v.user);
        else if (v.status === "mfa_required") handlers.current.onMfa(Boolean(v.enrollment_required));
        else if (v.status === "refused") setError(v.message);
        else if (v.status === "expired") setError(t.telegram.expired);
      },
      onError: (e) => setError(e instanceof ApiError && e.code !== "network" ? e.message : t.telegram.unavailable),
      onTimeout: () => setError(t.telegram.expired),
    });
    return () => {
      stop();
      clearInterval(tickTimer);
    };
  }, [data]);

  const back = (
    <Button variant="ghost" onClick={onCancel} block>
      {t.telegram.backToPassword}
    </Button>
  );

  if (error) {
    return (
      <div className="space-y-4">
        <Alert tone="error" action={<Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>{t.telegram.retry}</Button>}>
          {error}
        </Alert>
        {back}
      </div>
    );
  }

  if (!data) {
    return (
      <div role="status" className="flex justify-center py-8 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-center">
      <p className="text-ink-2">{t.telegram.instructions}</p>
      <p aria-live="polite" className="text-5xl font-bold tabular-nums tracking-widest text-ink">
        {data.match_code}
      </p>
      <p className="text-sm text-ink-muted">{countdown}</p>
      <a
        href={data.deep_link}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex min-h-tap w-full items-center justify-center rounded-xl bg-primary px-4 font-semibold text-white hover:bg-primary-hover"
      >
        <Send className="mr-2 h-5 w-5" aria-hidden />
        {t.telegram.openTelegram}
      </a>
      <img src={data.qr_svg} alt={t.telegram.qrAlt}
        className="mx-auto hidden h-40 w-40 rounded-xl ring-1 ring-line sm:block" />
      <p className="flex items-center justify-center text-sm text-ink-muted">
        <Spinner className="mr-2 h-4 w-4" />
        {t.telegram.waiting}
      </p>
      {back}
    </div>
  );
}
