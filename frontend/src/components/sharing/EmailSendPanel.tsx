import { useEffect, useId, useMemo, useState } from "react";
import { type FormEvent } from "react";
import { RefreshCw, Send } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type {
  EmailOptions,
  EmailSend,
  EmailSendStatus,
} from "../../api/types";
import type { ReportSelection } from "../../lib/reportQuery";
import { t, useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import {
  errorText,
  selectionPayload,
} from "../../lib/sharing";
import { RecipientPicker } from "./RecipientPicker";
import type { PickedRecipients } from "./RecipientPicker";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { Button } from "../Button";
import { Card } from "../Card";
import { EmptyState } from "../EmptyState";
import { Input } from "../Input";
import { Spinner } from "../Spinner";
import { useToast } from "../Toast";

function sendStatusBadge(status: EmailSendStatus) {
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

function deliveryStatusBadge(status: string) {
  const tone =
    status === "queued"
      ? "gray"
      : status === "sent"
        ? "green"
        : status === "failed"
          ? "red"
          : "amber";
  return (
    <Badge tone={tone}>{t.sharing.email.deliveryStatus[status]}</Badge>
  );
}

function linkCapReached(o: EmailOptions): boolean {
  return o.links_max !== undefined && (o.links_active ?? 0) >= o.links_max;
}

export function EmailSendPanel(props: {
  code: string;
  dashboardName: string;
  selection: ReportSelection | null;
  pdfAvailable: boolean;
  onSent?: () => void;
}) {
  const t = useT();
  const { code, dashboardName, selection, pdfAvailable, onSent } = props;
  const [options, setOptions] = useState<EmailOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [recipients, setRecipients] = useState<PickedRecipients>({
    users: [],
    emails: [],
  });
  const initialSubject = dashboardName.slice(0, 200);
  const [subject, setSubject] = useState(initialSubject);
  const [message, setMessage] = useState("");
  const [attachPdf, setAttachPdf] = useState(pdfAvailable);
  const [includeLink, setIncludeLink] = useState(false);
  const [linkDays, setLinkDays] = useState(7);
  const [recipientsError, setRecipientsError] = useState<string | null>(
    null,
  );
  const [linkDaysError, setLinkDaysError] = useState<string | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);
  const toast = useToast();
  const messageId = useId();

  const load = async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setLoadError(null);
    }
    try {
      const data = await api.get<EmailOptions>(
        `/api/dashboards/${encodeURIComponent(code)}/email`,
      );
      setOptions(data);
      if (!silent && data.link_days.default !== undefined) {
        setLinkDays(data.link_days.default);
      }
    } catch (e) {
      if (!silent) setLoadError(errorText(e));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  useEffect(() => {
    setSubject(dashboardName.slice(0, 200));
  }, [dashboardName]);

  const hasPending = useMemo(
    () =>
      options?.items.some(
        (send) =>
          send.status === "queued" || send.status === "sending",
      ) ?? false,
    [options],
  );

  useEffect(() => {
    if (!hasPending) return;
    const interval = setInterval(() => {
      void load(true);
    }, 10_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasPending, code]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setPostError(null);
    setRecipientsError(null);
    setLinkDaysError(null);
    if (!options) return;
    const wantsLink = options.can_link && includeLink && !linkCapReached(options);

    if (recipients.users.length === 0 && recipients.emails.length === 0) {
      setRecipientsError(t.sharing.email.noRecipients);
      return;
    }

    if (
      (!pdfAvailable || !attachPdf) &&
      !wantsLink
    ) {
      setPostError(t.sharing.email.nothingToSend);
      return;
    }

    if (wantsLink) {
      if (
        !Number.isInteger(linkDays) ||
        linkDays < options.link_days.min ||
        linkDays > options.link_days.max
      ) {
        setLinkDaysError(
          t.sharing.email.linkDaysRange(
            options.link_days.min,
            options.link_days.max,
          ),
        );
        return;
      }
    }

    setPosting(true);
    try {
      const send = await api.post<EmailSend>(
        `/api/dashboards/${encodeURIComponent(code)}/email`,
        {
          users: recipients.users.map((u) => u.id),
          emails: recipients.emails,
          subject: subject.trim() || null,
          message: message.trim() || null,
          selection: selection ? selectionPayload(selection) : null,
          attach_pdf: pdfAvailable && attachPdf,
          link_days: wantsLink ? linkDays : null,
        },
      );
      toast(t.sharing.email.queuedToast);
      setRecipients({ users: [], emails: [] });
      setSubject(initialSubject);
      setMessage("");
      if (options) {
        setOptions({ ...options, items: [send, ...options.items] });
      }
      onSent?.();
    } catch (e) {
      if (e instanceof ApiError && (e.status === 422 || e.status === 409)) {
        if (
          e.fields.users !== undefined ||
          e.fields.emails !== undefined ||
          e.fields.recipients !== undefined
        ) {
          setRecipientsError(e.message);
        } else if (e.fields.link_days !== undefined) {
          setLinkDaysError(e.message);
        } else {
          setPostError(errorText(e));
        }
      } else {
        setPostError(errorText(e));
      }
    } finally {
      setPosting(false);
    }
  };

  if (loading && !options) {
    return (
      <div role="status" className="flex justify-center py-8 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  if (loadError || !options) {
    return (
      <Alert
        tone="error"
        action={
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-5 w-5" aria-hidden />}
            onClick={() => void load(false)}
          >
            {t.common.retry}
          </Button>
        }
      >
        {loadError ?? t.common.unexpected}
      </Alert>
    );
  }

  const capReached = linkCapReached(options);

  return (
    <div className="space-y-8">
      {options.available ? (
        <Card tone="accent" className="p-5">
          <form onSubmit={(e) => void submit(e)} className="space-y-5">
            <RecipientPicker
              code={code}
              allowedDomains={options.allowed_domains}
              max={options.max_recipients}
              value={recipients}
              onChange={setRecipients}
              error={recipientsError}
            />

            <Input
              label={t.sharing.email.subject}
              hint={t.sharing.email.subjectHint}
              maxLength={200}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />

            <div>
              <label
                htmlFor={messageId}
                className="mb-1.5 block text-sm font-semibold text-ink-2"
              >
                {t.sharing.email.message}
              </label>
              <textarea
                id={messageId}
                rows={4}
                maxLength={2000}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="block w-full rounded-xl border border-transparent bg-field px-4 py-3 text-ink placeholder-ink-faint focus:outline-none focus:ring-2 focus:ring-field-focus"
              />
            </div>

            {pdfAvailable && (
              <label className="flex min-h-tap cursor-pointer items-center gap-2 text-sm font-semibold text-ink-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-primary"
                  checked={attachPdf}
                  onChange={(e) => setAttachPdf(e.target.checked)}
                />
                {t.sharing.email.attachPdf}
              </label>
            )}

            {options.can_link && (
              <div className="space-y-3">
                <label
                  className={`flex min-h-tap items-center gap-2 text-sm font-semibold text-ink-2 ${
                    capReached ? "cursor-not-allowed opacity-60" : "cursor-pointer"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={includeLink}
                    disabled={capReached}
                    onChange={(e) => setIncludeLink(e.target.checked)}
                  />
                  {t.sharing.email.includeLink}
                </label>
                {capReached && (
                  <p className="text-sm text-ink-muted">
                    {t.sharing.email.linkCapReached(options.links_max!)}
                  </p>
                )}
                {includeLink && !capReached && (
                  <div className="max-w-xs">
                    <Input
                      label={t.sharing.email.linkDays}
                      type="number"
                      value={linkDays}
                      onChange={(e) =>
                        setLinkDays(
                          e.target.value === ""
                            ? 0
                            : Number(e.target.value),
                        )
                      }
                      min={options.link_days.min}
                      max={options.link_days.max}
                      error={linkDaysError}
                    />
                  </div>
                )}
              </div>
            )}

            {selection && (
              <p className="text-sm text-ink-muted">
                {t.sharing.email.selectionNote(
                  t.reportParams.periodLabels[selection.period] ??
                    selection.period,
                )}
              </p>
            )}

            {postError && <Alert tone="error">{postError}</Alert>}

            <Button
              type="submit"
              variant="primary"
              icon={<Send className="h-5 w-5" aria-hidden />}
              loading={posting}
            >
              {t.sharing.email.send}
            </Button>
          </form>
        </Card>
      ) : (
        <Alert tone="info">{t.sharing.email.unavailable}</Alert>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-ink">
            {t.sharing.email.sends}
          </h2>
          <Button
            variant="ghost"
            icon={<RefreshCw className="h-5 w-5" aria-hidden />}
            onClick={() => void load(true)}
          >
            {t.sharing.email.refresh}
          </Button>
        </div>
        {options.items.length === 0 ? (
          <EmptyState title={t.sharing.email.noSends} />
        ) : (
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {options.items.map((send) => (
                <li key={send.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-ink">
                          {send.subject}
                        </p>
                        {sendStatusBadge(send.status)}
                        {send.subscription_id !== null && (
                          <Badge tone="accent">
                            {t.sharing.email.scheduledBadge}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-ink-muted">
                        {t.sharing.email.requestedBy(
                          send.requested_by?.name ?? "—",
                          formatDateTime(send.created_at),
                        )}
                      </p>
                      {send.deliveries.length > 0 && (
                        <ul className="space-y-1.5">
                          {send.deliveries.map((delivery) => (
                            <li
                              key={delivery.id}
                              className="text-sm text-ink"
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="break-all">
                                  {delivery.recipient}
                                </span>
                                {deliveryStatusBadge(delivery.status)}
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
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
