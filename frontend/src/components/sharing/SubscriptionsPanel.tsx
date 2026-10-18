import { useEffect, useRef, useState } from "react";
import { type FormEvent } from "react";
import {
  Pause,
  Pencil,
  Plus,
  Play,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Link } from "react-router";
import { api, ApiError } from "../../api/client";
import type {
  EmailOptions,
  ReportDefinition,
  Subscription,
  SubscriptionFrequency,
  SubscriptionsState,
  SubscriptionRecipient,
} from "../../api/types";
import type { PeriodPreset } from "../../api/types";
import { useT, type Catalogue } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { errorText, hourLabel, scheduleText } from "../../lib/sharing";
import { RecipientPicker } from "./RecipientPicker";
import type { PickedRecipients } from "./RecipientPicker";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { Button } from "../Button";
import { Card } from "../Card";
import { EmptyState } from "../EmptyState";
import { Input } from "../Input";
import { Select } from "../Select";
import { Spinner } from "../Spinner";
import { useToast } from "../Toast";

interface FormState {
  mode: "create" | "edit";
  id?: number;
  frequency: SubscriptionFrequency;
  hour: number;
  weekday: number;
  monthday: number;
  period: PeriodPreset;
  attachPdf: boolean;
  includeLink: boolean;
  linkDays: number;
  recipients: PickedRecipients;
}

function recipientsFromSubscription(
  sub: Subscription,
): PickedRecipients {
  const users: PickedRecipients["users"] = [];
  const emails: string[] = [];
  for (const recipient of sub.recipients) {
    if ("user_id" in recipient) {
      users.push({
        id: recipient.user_id,
        name: recipient.name ?? `#${recipient.user_id}`,
      });
    } else if ("email" in recipient) {
      emails.push(recipient.email);
    }
  }
  return { users, emails };
}

function recipientLabel(recipient: SubscriptionRecipient, t: Catalogue): string {
  if ("user_id" in recipient) {
    return recipient.name ?? `#${recipient.user_id}`;
  }
  if ("role" in recipient) {
    return t.sharing.schedules.roleRecipient(t.roles[recipient.role] ?? recipient.role);
  }
  return recipient.email;
}

export function SubscriptionsPanel(props: {
  code: string;
  def: ReportDefinition;
}) {
  const t = useT();
  const { code, def } = props;
  const [subs, setSubs] = useState<SubscriptionsState | null>(null);
  const [email, setEmail] = useState<EmailOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [recipientsError, setRecipientsError] = useState<string | null>(
    null,
  );
  const [linkDaysError, setLinkDaysError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const toast = useToast();
  const hasLoadedRef = useRef(false);

  const load = async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setLoadError(null);
    }
    try {
      const [subscriptions, emailOptions] = await Promise.all([
        api.get<SubscriptionsState>(
          `/api/dashboards/${encodeURIComponent(code)}/subscriptions`,
        ),
        api.get<EmailOptions>(
          `/api/dashboards/${encodeURIComponent(code)}/email`,
        ),
      ]);
      setSubs(subscriptions);
      setEmail(emailOptions);
      hasLoadedRef.current = true;
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

  const allowedPeriods = def.periods.allowed.filter(
    (p): p is PeriodPreset => p !== "custom",
  );

  const defaultPeriod: PeriodPreset =
    def.periods.default !== "custom" &&
    allowedPeriods.includes(def.periods.default)
      ? def.periods.default
      : (allowedPeriods[0] ?? "last_7_days");

  const emptyForm = (): FormState => ({
    mode: "create",
    frequency: "daily",
    hour: 8,
    weekday: 0,
    monthday: 1,
    period: defaultPeriod,
    attachPdf: def.pdf,
    includeLink: false,
    linkDays: email?.link_days.default ?? 7,
    recipients: { users: [], emails: [] },
  });

  const openCreate = () => {
    setForm(emptyForm());
    setFormError(null);
    setRecipientsError(null);
    setLinkDaysError(null);
  };

  const openEdit = (sub: Subscription) => {
    setForm({
      mode: "edit",
      id: sub.id,
      frequency: sub.frequency,
      hour: sub.hour,
      weekday: sub.weekday ?? 0,
      monthday: sub.monthday ?? 1,
      period: sub.period,
      attachPdf: sub.attach_pdf,
      includeLink: sub.link_days !== null,
      linkDays: sub.link_days ?? email?.link_days.default ?? 7,
      recipients: recipientsFromSubscription(sub),
    });
    setFormError(null);
    setRecipientsError(null);
    setLinkDaysError(null);
  };

  const closeForm = () => {
    setForm(null);
    setFormError(null);
    setRecipientsError(null);
    setLinkDaysError(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form || !subs || !email) return;
    setFormError(null);
    setRecipientsError(null);
    setLinkDaysError(null);

    if (
      form.recipients.users.length === 0 &&
      form.recipients.emails.length === 0
    ) {
      setRecipientsError(t.sharing.email.noRecipients);
      return;
    }
    if (
      (!def.pdf || !form.attachPdf) &&
      !(subs.can_link && form.includeLink)
    ) {
      setFormError(t.sharing.email.nothingToSend);
      return;
    }
    if (subs.can_link && form.includeLink) {
      if (
        !Number.isInteger(form.linkDays) ||
        form.linkDays < email.link_days.min ||
        form.linkDays > email.link_days.max
      ) {
        setLinkDaysError(
          t.sharing.email.linkDaysRange(
            email.link_days.min,
            email.link_days.max,
          ),
        );
        return;
      }
    }

    const body = {
      frequency: form.frequency,
      hour: form.hour,
      weekday:
        form.frequency === "weekly" ? form.weekday : null,
      monthday:
        form.frequency === "monthly" ? form.monthday : null,
      period: form.period,
      attach_pdf: def.pdf && form.attachPdf,
      link_days:
        subs.can_link && form.includeLink ? form.linkDays : null,
      users: form.recipients.users.map((u) => u.id),
      emails: form.recipients.emails,
    };

    setSaving(true);
    try {
      if (form.mode === "create") {
        await api.post<Subscription>(
          `/api/dashboards/${encodeURIComponent(code)}/subscriptions`,
          body,
        );
        toast(t.sharing.schedules.createdToast);
      } else if (form.id !== undefined) {
        await api.patch<Subscription>(
          `/api/dashboards/${encodeURIComponent(code)}/subscriptions/${form.id}`,
          body,
        );
        toast(t.sharing.schedules.updatedToast);
      }
      closeForm();
      await load(true);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        if (
          e.fields.users !== undefined ||
          e.fields.emails !== undefined ||
          e.fields.recipients !== undefined
        ) {
          setRecipientsError(e.message);
        } else {
          setFormError(e.message);
        }
      } else {
        setFormError(errorText(e));
      }
    } finally {
      setSaving(false);
    }
  };

  const togglePaused = async (sub: Subscription) => {
    setBusyId(sub.id);
    setActionError(null);
    try {
      await api.patch<Subscription>(
        `/api/dashboards/${encodeURIComponent(code)}/subscriptions/${sub.id}`,
        { paused: !sub.paused },
      );
      toast(t.sharing.schedules.updatedToast);
      await load(true);
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (sub: Subscription) => {
    setBusyId(sub.id);
    setActionError(null);
    try {
      await api.del(
        `/api/dashboards/${encodeURIComponent(code)}/subscriptions/${sub.id}`,
      );
      toast(t.sharing.schedules.deletedToast);
      if (form?.mode === "edit" && form.id === sub.id) {
        closeForm();
      }
      setConfirmingId(null);
      await load(true);
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  if (loading && !hasLoadedRef.current) {
    return (
      <div role="status" className="flex justify-center py-8 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  if (loadError || !subs || !email) {
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

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">
          {t.sharing.schedules.timezoneNote(subs.timezone)}
        </p>
        {subs.available && !form && (
          <Button
            variant="primary"
            icon={<Plus className="h-5 w-5" aria-hidden />}
            onClick={openCreate}
          >
            {t.sharing.schedules.newSchedule}
          </Button>
        )}
      </div>

      {!subs.available && <Alert tone="info">{t.sharing.email.unavailable}</Alert>}

      {form && subs.available && (
        <Card tone="accent" className="p-5">
          <h2 className="mb-4 text-base font-semibold text-ink">
            {form.mode === "create"
              ? t.sharing.schedules.newSchedule
              : t.sharing.schedules.editSchedule}
          </h2>
          <form onSubmit={(e) => void submit(e)} className="space-y-5">
            <Select
              label={t.sharing.schedules.frequency}
              value={form.frequency}
              onChange={(e) =>
                setForm({
                  ...form,
                  frequency: e.target.value as SubscriptionFrequency,
                })
              }
            >
              <option value="daily">
                {t.sharing.schedules.frequencyLabels.daily}
              </option>
              <option value="weekly">
                {t.sharing.schedules.frequencyLabels.weekly}
              </option>
              <option value="monthly">
                {t.sharing.schedules.frequencyLabels.monthly}
              </option>
            </Select>

            <Select
              label={t.sharing.schedules.hour}
              value={form.hour}
              onChange={(e) =>
                setForm({ ...form, hour: Number(e.target.value) })
              }
            >
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {hourLabel(h)}
                </option>
              ))}
            </Select>

            {form.frequency === "weekly" && (
              <Select
                label={t.sharing.schedules.weekday}
                value={form.weekday}
                onChange={(e) =>
                  setForm({ ...form, weekday: Number(e.target.value) })
                }
              >
                {t.sharing.schedules.weekdays.map((day, index) => (
                  <option key={index} value={index}>
                    {day}
                  </option>
                ))}
              </Select>
            )}

            {form.frequency === "monthly" && (
              <Select
                label={t.sharing.schedules.monthday}
                hint={t.sharing.schedules.monthdayHint}
                value={form.monthday}
                onChange={(e) =>
                  setForm({ ...form, monthday: Number(e.target.value) })
                }
              >
                {Array.from({ length: 28 }, (_, d) => (
                  <option key={d + 1} value={d + 1}>
                    {d + 1}
                  </option>
                ))}
              </Select>
            )}

            <Select
              label={t.sharing.schedules.period}
              value={form.period}
              onChange={(e) =>
                setForm({
                  ...form,
                  period: e.target.value as PeriodPreset,
                })
              }
            >
              {allowedPeriods.map((period) => (
                <option key={period} value={period}>
                  {t.reportParams.periodLabels[period] ?? period}
                </option>
              ))}
            </Select>

            {def.pdf && (
              <label className="flex min-h-tap cursor-pointer items-center gap-2 text-sm font-semibold text-ink-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-primary"
                  checked={form.attachPdf}
                  onChange={(e) =>
                    setForm({ ...form, attachPdf: e.target.checked })
                  }
                />
                {t.sharing.schedules.attachPdf}
              </label>
            )}

            {subs.can_link && (
              <div className="space-y-3">
                <label className="flex min-h-tap cursor-pointer items-center gap-2 text-sm font-semibold text-ink-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-primary"
                    checked={form.includeLink}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        includeLink: e.target.checked,
                      })
                    }
                  />
                  {t.sharing.email.includeLink}
                </label>
                {form.includeLink && (
                  <div className="max-w-xs">
                    <Input
                      label={t.sharing.email.linkDays}
                      type="number"
                      value={form.linkDays}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          linkDays:
                            e.target.value === ""
                              ? 0
                              : Number(e.target.value),
                        })
                      }
                      min={email.link_days.min}
                      max={email.link_days.max}
                      error={linkDaysError}
                    />
                  </div>
                )}
              </div>
            )}

            <RecipientPicker
              code={code}
              allowedDomains={email.allowed_domains}
              max={email.max_recipients}
              value={form.recipients}
              onChange={(recipients) => setForm({ ...form, recipients })}
              error={recipientsError}
            />

            {formError && <Alert tone="error">{formError}</Alert>}

            <div className="flex flex-wrap gap-3">
              <Button type="submit" variant="primary" loading={saving}>
                {t.sharing.schedules.save}
              </Button>
              <Button variant="secondary" onClick={closeForm}>
                {t.common.cancel}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {actionError && <Alert tone="error">{actionError}</Alert>}

      <section>
        <h2 className="mb-3 text-base font-semibold text-ink">
          {t.sharing.schedules.listTitle}
        </h2>
        {subs.items.length === 0 ? (
          <EmptyState title={t.sharing.schedules.noSchedules} />
        ) : (
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {subs.items.map((sub) => (
                <li key={sub.id} className="px-5 py-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-ink">
                        {scheduleText(sub)}
                      </p>
                      <span className="text-ink-muted">
                        · {sub.period_label}
                      </span>
                      {sub.paused && (
                        <Badge tone="gray">
                          {t.sharing.schedules.paused}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-ink-muted">
                      {!sub.paused &&
                        t.sharing.schedules.nextRun(
                          formatDateTime(sub.next_due_at, subs.timezone),
                        )}
                      {!sub.paused && sub.last_due_at && " · "}
                      {sub.last_due_at &&
                        t.sharing.schedules.lastRun(
                          formatDateTime(sub.last_due_at, subs.timezone),
                        )}
                    </p>
                    <p className="text-sm text-ink-muted">
                      {t.sharing.schedules.recipientsLine(
                        sub.recipients.map((r) => recipientLabel(r, t)).join(", "),
                      )}
                    </p>
                    {sub.managed_by && (
                      <p className="text-sm text-ink-muted">
                        {sub.managed_by.slug ? (
                          <Link
                            to={`/proyectos/${sub.managed_by.slug}`}
                            className="font-medium underline decoration-line-strong underline-offset-2 hover:text-accent"
                          >
                            {t.sharing.schedules.managedBy(
                              sub.managed_by.project ?? sub.managed_by.slug,
                            )}
                          </Link>
                        ) : (
                          t.sharing.schedules.managedBy(sub.managed_by.distribution)
                        )}
                        {" · "}
                        {t.sharing.schedules.managedHint}
                      </p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      {subs.available && !sub.managed_by && (
                        <Button
                          variant="secondary"
                          icon={<Pencil className="h-5 w-5" aria-hidden />}
                          disabled={busyId === sub.id}
                          onClick={() => openEdit(sub)}
                        >
                          {t.sharing.schedules.edit}
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        icon={
                          sub.paused ? (
                            <Play className="h-5 w-5" aria-hidden />
                          ) : (
                            <Pause className="h-5 w-5" aria-hidden />
                          )
                        }
                        disabled={busyId === sub.id}
                        onClick={() => void togglePaused(sub)}
                      >
                        {sub.paused
                          ? t.sharing.schedules.resume
                          : t.sharing.schedules.pause}
                      </Button>
                      {sub.managed_by ? null : confirmingId === sub.id ? (
                        <div className="flex gap-2">
                          <Button
                            variant="danger"
                            loading={busyId === sub.id}
                            onClick={() => void remove(sub)}
                          >
                            {t.sharing.schedules.confirmDelete}
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => setConfirmingId(null)}
                          >
                            {t.common.cancel}
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="secondary"
                          icon={<Trash2 className="h-5 w-5" aria-hidden />}
                          disabled={busyId === sub.id}
                          onClick={() => setConfirmingId(sub.id)}
                        >
                          {t.sharing.schedules.delete}
                        </Button>
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
