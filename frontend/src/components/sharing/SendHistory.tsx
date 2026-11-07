import { useEffect, useState } from "react";
import { RefreshCw, Send } from "lucide-react";
import { api } from "../../api/client";
import type { EmailSend, EmailSendStatus } from "../../api/types";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { errorText } from "../../lib/sharing";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { Button } from "../Button";
import { Card } from "../Card";
import { EmptyState } from "../EmptyState";
import { Spinner } from "../Spinner";
import { useToast } from "../Toast";

function SendStatusBadge({ status }: { status: EmailSendStatus }) {
  const t = useT();
  const tone =
    status === "queued"
      ? "gray"
      : status === "sending"
        ? "accent"
        : status === "sent"
          ? "green"
          : status === "partial"
            ? "amber"
            : "red";
  return <Badge tone={tone}>{t.sharing.email.sendStatus[status]}</Badge>;
}

function DeliveryStatusBadge({ status }: { status: string }) {
  const t = useT();
  const tone =
    status === "queued" ? "gray" : status === "sent" ? "green" : status === "failed" ? "red" : "amber";
  return <Badge tone={tone}>{t.sharing.email.deliveryStatus[status]}</Badge>;
}

/**
 * Feature 058: the send history — date, sender, the kinds of recipients (counts and list names,
 * never addresses), the status of every address and the re-send of the failed ones.
 */
export function SendHistory(props: {
  code: string;
  sends: EmailSend[];
  onResent?: (send: EmailSend) => void;
}) {
  const t = useT();
  const { code, sends, onResent } = props;
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const toast = useToast();

  const resendFailed = async (send: EmailSend) => {
    setBusyId(send.id);
    setActionError(null);
    try {
      const resent = await api.post<EmailSend>(
        `/api/dashboards/${encodeURIComponent(code)}/email/sends/${send.id}/resend-failed`,
      );
      toast(t.sharing.email.resentToast);
      onResent?.(resent);
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  if (sends.length === 0) return <EmptyState title={t.sharing.email.noSends} />;

  return (
    <div className="space-y-4">
      {actionError && <Alert tone="error">{actionError}</Alert>}
      <Card className="p-0">
        <ul className="divide-y divide-line">
          {sends.map((send) => {
            const failed = send.deliveries.filter((d) => d.status === "failed").length;
            const kinds = send.kinds ?? {};
            const kindParts: string[] = [];
            if (kinds.users) kindParts.push(t.sharing.email.kinds.users(kinds.users));
            if (kinds.lists && kinds.lists.length > 0) {
              kindParts.push(t.sharing.email.kinds.lists(kinds.lists.join(", ")));
            }
            if (kinds.emails) kindParts.push(t.sharing.email.kinds.emails(kinds.emails));
            return (
              <li key={send.id} className="px-5 py-4">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-ink">{send.subject}</p>
                    <SendStatusBadge status={send.status} />
                    {send.subscription_id !== null && (
                      <Badge tone="accent">{t.sharing.email.scheduledBadge}</Badge>
                    )}
                    {failed > 0 && <Badge tone="red">{t.sharing.email.failedCount(failed)}</Badge>}
                  </div>
                  <p className="text-sm text-ink-muted">
                    {t.sharing.email.requestedBy(
                      send.requested_by?.name ?? "—",
                      formatDateTime(send.created_at),
                    )}
                    {" · "}
                    {t.sharing.email.recipientCount(send.count ?? send.deliveries.length)}
                  </p>
                  {kindParts.length > 0 && (
                    <p className="text-sm text-ink-muted">{kindParts.join(" · ")}</p>
                  )}
                  {send.deliveries.length > 0 && (
                    <ul className="space-y-1.5">
                      {send.deliveries.map((delivery) => (
                        <li key={delivery.id} className="text-sm text-ink">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="break-all">{delivery.recipient}</span>
                            <DeliveryStatusBadge status={delivery.status} />
                          </div>
                          {delivery.error && (
                            <p className="mt-1 text-sm text-danger">
                              {delivery.error}
                              {delivery.attempts > 0 &&
                                ` · ${t.sharing.email.attempts(delivery.attempts)}`}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {failed > 0 && (
                    <Button
                      variant="secondary"
                      icon={<Send className="h-5 w-5" aria-hidden />}
                      loading={busyId === send.id}
                      onClick={() => void resendFailed(send)}
                    >
                      {t.sharing.email.resendFailed}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}

/** The `⋯ → Envíos` screen: the same history, with its own fetch and refresh. */
export function SendHistoryPanel(props: { code: string; onResent?: (send: EmailSend) => void }) {
  const t = useT();
  const { code, onResent } = props;
  const [sends, setSends] = useState<EmailSend[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.get<{ items: EmailSend[] }>(
        `/api/dashboards/${encodeURIComponent(code)}/email/sends?limit=50`,
      );
      setSends(data.items);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  if (loading && sends === null) {
    return (
      <div role="status" className="flex justify-center py-8 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          variant="ghost"
          icon={<RefreshCw className="h-5 w-5" aria-hidden />}
          onClick={() => void load(false)}
        >
          {t.sharing.email.refresh}
        </Button>
      </div>
      {error ? (
        <Alert
          tone="error"
          action={
            <Button variant="secondary" onClick={() => void load(false)}>
              {t.common.retry}
            </Button>
          }
        >
          {error}
        </Alert>
      ) : null}
      <SendHistory
        code={code}
        sends={sends ?? []}
        onResent={(send) => {
          setSends((current) => [send, ...(current ?? [])]);
          onResent?.(send);
        }}
      />
    </div>
  );
}
