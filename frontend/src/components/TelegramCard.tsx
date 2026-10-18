import { CheckCircle2, Send, Unlink } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { MeTelegram, TelegramLinkStart } from "../api/types";
import { useBranding } from "../config/BrandingContext";
import { t, useT } from "../i18n";
import { dateTimeFormat } from "../lib/intl";
import { startPolling } from "../lib/telegramPoll";
import { Alert } from "./Alert";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { Spinner } from "./Spinner";
import { useToast } from "./Toast";

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : t.common.unexpected);

/** Profile: link or unlink the user's own Telegram (feature 007, US2). Hidden while the
 * installation has Telegram sign-in off. */
export function TelegramCard() {
  const t = useT();
  const { telegram_sign_in } = useBranding();
  const toast = useToast();
  const [me, setMe] = useState<MeTelegram | null>(null);
  const [linkStart, setLinkStart] = useState<TelegramLinkStart | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setMe(await api.get<MeTelegram>("/api/me/telegram"));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  useEffect(() => {
    if (telegram_sign_in) void load();
  }, [telegram_sign_in, load]);

  useEffect(() => {
    if (!linkStart) return;
    return startPolling<MeTelegram>({
      fetch: () => api.get<MeTelegram>("/api/me/telegram"),
      isFinal: (v) => v.linked,
      onValue: (v) => {
        if (!v.linked) return;
        setMe(v);
        setLinkStart(null);
        toast(t.telegram.linked);
      },
      onError: (e) => {
        setLinkStart(null);
        setError(errorText(e));
      },
      onTimeout: () => {
        setLinkStart(null);
        setError(t.telegram.expired);
      },
    });
  }, [linkStart, toast]);

  if (!telegram_sign_in) return null;

  const startLink = async () => {
    setBusy(true);
    setError(null);
    try {
      setLinkStart(await api.post<TelegramLinkStart>("/api/me/telegram/link"));
    } catch (e) {
      if (e instanceof ApiError && e.code === "telegram_already_linked_self") await load();
      else setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.del("/api/me/telegram");
      toast(t.telegram.unlinked);
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const linkedName = me?.display_name || me?.username || "Telegram";

  return (
    <Card className="p-4 sm:p-6">
      <h2 className="mb-3 text-lg font-semibold">{t.telegram.profileTitle}</h2>
      {error ? <div className="mb-3"><Alert tone="error">{error}</Alert></div> : null}
      {!me ? (
        <Spinner className="h-5 w-5 text-accent" />
      ) : me.linked ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center">
            <Badge tone="green" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>
              {t.telegram.linkedAs(linkedName)}
            </Badge>
            {me.username ? <span className="ml-2 text-sm text-ink-muted">@{me.username}</span> : null}
          </div>
          {me.linked_at ? (
            <p className="text-sm text-ink-muted">
              {t.telegram.since(dateTimeFormat({ day: "numeric", month: "short", year: "numeric" }).format(new Date(me.linked_at)))}
            </p>
          ) : null}
          <Button variant="secondary" icon={<Unlink className="h-5 w-5" aria-hidden />} onClick={unlink} loading={busy}>
            {t.telegram.unlink}
          </Button>
        </div>
      ) : linkStart ? (
        <div className="space-y-3 text-center">
          <a
            href={linkStart.deep_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-tap w-full items-center justify-center rounded-xl bg-primary px-4 font-semibold text-white hover:bg-primary-hover sm:w-auto"
          >
            <Send className="mr-2 h-5 w-5" aria-hidden />
            {t.telegram.openTelegram}
          </a>
          <img src={linkStart.qr_svg} alt={t.telegram.qrAlt}
            className="mx-auto hidden h-40 w-40 rounded-xl ring-1 ring-line sm:block" />
          <p className="text-sm text-ink-muted">{t.telegram.linkHint}</p>
          <p className="flex items-center justify-center text-sm text-ink-muted">
            <Spinner className="mr-2 h-4 w-4" />
            {t.telegram.waiting}
          </p>
        </div>
      ) : (
        <Button icon={<Send className="h-5 w-5" aria-hidden />} onClick={startLink} loading={busy}>
          {t.telegram.link}
        </Button>
      )}
    </Card>
  );
}
