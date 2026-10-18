import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  Clock,
  Pause,
  Play,
  PlayCircle,
  RefreshCw,
  Square,
  Workflow,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useId, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Integration, IntegrationControl, IntegrationControlUpdate, IntegrationRun } from "../../api/types";
import { Alert } from "../../components/Alert";
import { BackLink } from "../../components/BackLink";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { CodeChip } from "../../components/CodeChip";
import { EmptyState } from "../../components/EmptyState";
import { IconButton } from "../../components/IconButton";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { View } from "../../components/View";
import { useT } from "../../i18n";
import { formatDateTime } from "../../lib/format";
import { datasetSummary, rollupSummary } from "../../lib/integrationRuns";
import {
  cronFromPreset,
  describeCron,
  frequencyWords,
  fullRebuildOutsideWindow,
  normalizeCron,
  presetFromCron,
  type PresetId,
} from "../../lib/schedule";

export function RunStatus({ run }: { run: IntegrationRun | null }) {
  const t = useT();
  if (!run) return <Badge tone="gray" icon={<Clock className="h-3.5 w-3.5" aria-hidden />}>{t.integrations.page.noRunsBadge}</Badge>;
  if (run.status === "succeeded") return <Badge tone="green" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>{t.integrations.runBadge.ok}</Badge>;
  if (run.status === "failed") return <Badge tone="red" icon={<XCircle className="h-3.5 w-3.5" aria-hidden />}>{t.integrations.runBadge.failed}</Badge>;
  if (run.status === "skipped") return <Badge tone="amber" icon={<AlertTriangle className="h-3.5 w-3.5" aria-hidden />}>{t.integrations.runBadge.skipped}</Badge>;
  if (run.status === "stopped") return <Badge tone="gray" icon={<Square className="h-3.5 w-3.5" aria-hidden />}>{t.integrations.runStopped}</Badge>;
  return <Badge tone="blue" icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden />}>{t.integrations.runBadge.running}</Badge>;
}

function Runs({ id }: { id: string }) {
  const t = useT();
  const [runs, setRuns] = useState<IntegrationRun[] | null>(null);
  useEffect(() => {
    api
      .get<{ items: IntegrationRun[] }>(`/api/integrations/${encodeURIComponent(id)}/runs?limit=10`)
      .then((r) => setRuns(r.items))
      .catch(() => setRuns([]));
  }, [id]);
  if (!runs) return <Spinner className="h-5 w-5 text-accent" />;
  if (!runs.length) return <p className="text-sm text-ink-muted">{t.integrations.page.noRuns}</p>;
  return (
    <ul className="space-y-2">
      {runs.map((r) => (
        <li key={r.id} className="rounded-xl border border-line bg-subtle p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <RunStatus run={r} />
            <span className="text-ink-3">
              {t.integrations.kinds[r.kind] ?? r.kind} · {formatDateTime(r.started_at)}
            </span>
          </div>
          <p className="mt-1 text-ink-3 [overflow-wrap:anywhere]">
            {Object.entries(r.rows)
              .map(([ds, n]) => datasetSummary(ds, n))
              .join(" · ") || "—"}
          </p>
          {rollupSummary(r.rollups) ? <p className="mt-1 text-ink-3 [overflow-wrap:anywhere]">{rollupSummary(r.rollups)}</p> : null}
          {r.message ? <p className="mt-1 text-danger-strong [overflow-wrap:anywhere]">{r.message}</p> : null}
          {r.checks
            .filter((c) => !c.ok)
            .map((c, i) => (
              <p key={i} className="mt-1 text-warning-deep [overflow-wrap:anywhere]">
                {c.dataset} · {c.type}: {c.detail}
              </p>
            ))}
        </li>
      ))}
    </ul>
  );
}

interface FormErrors {
  form?: string;
  schedule?: string;
  full_rebuild_cron?: string;
  window_start?: string;
  window_end?: string;
  dailyTime?: string;
}

function FrequencyForm({
  integration,
  busy,
  onSubmit,
  onRestore,
  onCancel,
}: {
  integration: Integration;
  busy: boolean;
  onSubmit: (body: IntegrationControlUpdate) => Promise<void>;
  onRestore: () => Promise<void>;
  onCancel: () => void;
}) {
  const t = useT();
  const control = integration.control;
  const initial = presetFromCron(control.schedule);
  const [preset, setPreset] = useState<PresetId>(initial.preset);
  const [time, setTime] = useState(initial.preset === "daily" ? initial.time : "03:00");
  const [custom, setCustom] = useState(initial.custom);
  const [windowOn, setWindowOn] = useState(control.window !== null);
  const [windowStart, setWindowStart] = useState(control.window?.start ?? "06:00");
  const [windowEnd, setWindowEnd] = useState(control.window?.end ?? "22:00");
  const [fullRebuild, setFullRebuild] = useState(control.full_rebuild_cron ?? "");
  const [errors, setErrors] = useState<FormErrors>({});

  const radioName = useId();

  const fieldError = (code: string): string | undefined => {
    const e = errors[code as keyof FormErrors];
    return typeof e === "string" ? e : undefined;
  };

  const submit = async () => {
    setErrors({});
    const next: FormErrors = {};
    if (preset === "custom" && !normalizeCron(custom)) {
      next.schedule = t.common.required;
    }
    if (preset === "daily" && !time) {
      next.dailyTime = t.common.required;
    }
    if (windowOn && (!windowStart || !windowEnd)) {
      next.window_start = t.integrations.errors.window_incomplete;
    }
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }

    const cron = cronFromPreset(preset, time, custom);
    const body: IntegrationControlUpdate = {
      schedule: cron === normalizeCron(control.spec_schedule) ? null : cron,
      full_rebuild_cron: normalizeCron(fullRebuild).length > 0 ? normalizeCron(fullRebuild) : null,
      window_start: windowOn ? windowStart : null,
      window_end: windowOn ? windowEnd : null,
    };

    try {
      await onSubmit(body);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422 && e.fields) {
        const mapped: FormErrors = { form: e.message };
        for (const [field, code] of Object.entries(e.fields)) {
          mapped[field as keyof FormErrors] = t.integrations.errors[code] ?? e.message;
        }
        setErrors(mapped);
      } else {
        setErrors({ form: e instanceof ApiError ? e.message : t.common.unexpected });
      }
    }
  };

  const restore = async () => {
    setErrors({});
    try {
      await onRestore();
    } catch (e) {
      setErrors({ form: e instanceof ApiError ? e.message : t.common.unexpected });
    }
  };

  const fullOutside = fullRebuildOutsideWindow(
    normalizeCron(fullRebuild).length > 0
      ? [normalizeCron(fullRebuild)]
      : control.spec_full_rebuild_crons,
    windowOn && windowStart && windowEnd ? { start: windowStart, end: windowEnd } : null,
  );

  const optionClass = (selected: boolean) =>
    `flex min-h-tap cursor-pointer items-center gap-2 rounded-xl border px-3 text-sm font-semibold focus-within:ring-2 focus-within:ring-field-focus ${
      selected ? "border-accent bg-accent-soft text-accent" : "border-line bg-field text-ink-2"
    }`;

  const canRestore = control.schedule_source === "override" || control.full_rebuild_source === "override";

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      className="space-y-5"
    >
      {errors.form ? <Alert tone="error">{errors.form}</Alert> : null}

      <p className="text-sm text-ink-soft">
        {t.integrations.form.specSchedule(frequencyWords(control.spec_schedule))}
      </p>

      <fieldset className="space-y-2">
        <legend className="text-sm font-semibold text-ink">{t.integrations.form.presetLegend}</legend>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label className={optionClass(preset === "every15")}>
            <input
              type="radio"
              name={radioName}
              value="every15"
              checked={preset === "every15"}
              onChange={() => setPreset("every15")}
              className="h-4 w-4 accent-primary"
            />
            {t.integrations.form.every15}
          </label>
          <label className={optionClass(preset === "every30")}>
            <input
              type="radio"
              name={radioName}
              value="every30"
              checked={preset === "every30"}
              onChange={() => setPreset("every30")}
              className="h-4 w-4 accent-primary"
            />
            {t.integrations.form.every30}
          </label>
          <label className={optionClass(preset === "hourly")}>
            <input
              type="radio"
              name={radioName}
              value="hourly"
              checked={preset === "hourly"}
              onChange={() => setPreset("hourly")}
              className="h-4 w-4 accent-primary"
            />
            {t.integrations.form.hourly}
          </label>
          <label className={optionClass(preset === "daily")}>
            <input
              type="radio"
              name={radioName}
              value="daily"
              checked={preset === "daily"}
              onChange={() => setPreset("daily")}
              className="h-4 w-4 accent-primary"
            />
            {t.integrations.form.daily}
          </label>
          <label className={optionClass(preset === "custom")}>
            <input
              type="radio"
              name={radioName}
              value="custom"
              checked={preset === "custom"}
              onChange={() => setPreset("custom")}
              className="h-4 w-4 accent-primary"
            />
            {t.integrations.form.custom}
          </label>
        </div>
      </fieldset>

      {preset === "daily" ? (
        <Input
          type="time"
          label={t.integrations.form.dailyTime}
          value={time}
          onChange={(e) => setTime(e.target.value)}
          required
          error={fieldError("dailyTime")}
        />
      ) : null}

      {preset === "custom" ? (
        <Input
          label={t.integrations.form.customLabel}
          hint={t.integrations.form.customHint}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          required
          error={fieldError("schedule")}
        />
      ) : null}

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold text-ink">{t.integrations.form.windowLegend}</legend>
        <label className="flex min-h-tap cursor-pointer items-center gap-2 text-sm font-semibold text-ink-2">
          <input
            type="checkbox"
            checked={windowOn}
            onChange={(e) => setWindowOn(e.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          {t.integrations.form.windowToggle}
        </label>
        {windowOn ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              type="time"
              label={t.integrations.form.windowFrom}
              value={windowStart}
              onChange={(e) => setWindowStart(e.target.value)}
              required
              error={fieldError("window_start")}
            />
            <Input
              type="time"
              label={t.integrations.form.windowTo}
              value={windowEnd}
              onChange={(e) => setWindowEnd(e.target.value)}
              required
              error={fieldError("window_end")}
            />
          </div>
        ) : null}
        <p className="text-sm text-ink-soft">{t.integrations.form.windowHint}</p>
        {fullOutside !== null ? (
          <p className="flex items-start gap-2 text-sm text-warning-deep">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {t.integrations.labels.fullRebuildOutsideWindow(fullOutside)}
          </p>
        ) : null}
      </fieldset>

      <Input
        label={t.integrations.form.fullRebuildLabel}
        hint={t.integrations.form.fullRebuildHint(
          control.spec_full_rebuild_crons.length
            ? control.spec_full_rebuild_crons.map((c) => frequencyWords(c)).join(", ")
            : null
        )}
        value={fullRebuild}
        onChange={(e) => setFullRebuild(e.target.value)}
        autoComplete="off"
        spellCheck={false}
        error={fieldError("full_rebuild_cron")}
      />

      <div className="space-y-1">
        <Button
          type="button"
          variant="ghost"
          onClick={() => void restore()}
          disabled={!canRestore || busy}
        >
          {t.integrations.form.restoreSpec}
        </Button>
        <p className="text-sm text-ink-soft">{t.integrations.form.restoreHint}</p>
      </div>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          {t.common.cancel}
        </Button>
        <Button type="submit" loading={busy}>
          {t.integrations.form.save}
        </Button>
      </div>
    </form>
  );
}

export function Integrations() {
  const t = useT();
  const toast = useToast();
  const [items, setItems] = useState<Integration[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<Integration | null>(null);
  const [pendingRun, setPendingRun] = useState<{
    id: string;
    lastRunId: number | null;
    until: number;
  } | null>(null);

  const load = useCallback(() => {
    api
      .get<{ items: Integration[] }>("/api/integrations")
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected));
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const hasRunning = items?.some((it) => it.running_run_id !== null) ?? false;
    if (!hasRunning || editing !== null) return;
    const timer = setInterval(load, 10_000);
    return () => clearInterval(timer);
  }, [items, editing, load]);

  useEffect(() => {
    if (pendingRun === null) return;
    const timer = setInterval(() => {
      if (Date.now() >= pendingRun.until) {
        setPendingRun(null);
        return;
      }
      load();
    }, 2000);
    return () => clearInterval(timer);
  }, [pendingRun, load]);

  useEffect(() => {
    if (pendingRun === null) return;

    if (Date.now() >= pendingRun.until) {
      setPendingRun(null);
      return;
    }

    const current = items?.find((it) => it.id === pendingRun.id);
    if (!current) return;

    const appeared =
      current.running_run_id !== null ||
      (current.last_run?.id ?? null) !== pendingRun.lastRunId;

    if (appeared) setPendingRun(null);
  }, [items, pendingRun]);

  const updateControl = (id: string, control: IntegrationControl) => {
    setItems((prev) =>
      prev
        ? prev.map((it) =>
            it.id === id ? { ...it, control, next_run: control.next_run } : it
          )
        : prev
    );
  };

  const run = (id: string, kind: "incremental" | "full") => {
    const lastRunId = items?.find((it) => it.id === id)?.last_run?.id ?? null;
    setBusy(`${id}:${kind}`);
    setError(null);
    api
      .post(`/api/integrations/${encodeURIComponent(id)}/run`, { kind })
      .then(() => {
        toast(t.integrations.toasts.runRequested);
        setPendingRun({ id, lastRunId, until: Date.now() + 30_000 });
        load();
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected))
      .finally(() => setBusy(null));
  };

  const togglePaused = (it: Integration) => {
    const nextPaused = !it.control.paused;
    setBusy(`${it.id}:pause`);
    setError(null);
    api
      .put<{ control: IntegrationControl }>(`/api/integrations/${encodeURIComponent(it.id)}/control`, {
        paused: nextPaused,
      } satisfies IntegrationControlUpdate)
      .then((r) => {
        updateControl(it.id, r.control);
        toast(nextPaused ? t.integrations.toasts.paused : t.integrations.toasts.resumed);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : t.common.unexpected))
      .finally(() => setBusy(null));
  };

  const stopRun = (it: Integration) => {
    if (it.running_run_id === null) return;
    setBusy(`${it.id}:stop`);
    setError(null);
    api
      .post(`/api/integrations/${encodeURIComponent(it.id)}/runs/${it.running_run_id}/stop`)
      .then(() => {
        toast(t.integrations.toasts.stopRequested);
        load();
      })
      .catch((e) => {
        setError(e instanceof ApiError ? e.message : t.common.unexpected);
        load();
      })
      .finally(() => setBusy(null));
  };

  const submitControl = async (it: Integration, body: IntegrationControlUpdate): Promise<void> => {
    setBusy(`${it.id}:save`);
    try {
      const r = await api.put<{ control: IntegrationControl }>(
        `/api/integrations/${encodeURIComponent(it.id)}/control`,
        body
      );
      updateControl(it.id, r.control);
      setEditing(null);
      toast(t.integrations.toasts.saved);
    } finally {
      setBusy(null);
    }
  };

  const restoreSpec = async (it: Integration): Promise<void> => {
    setBusy(`${it.id}:restore`);
    try {
      const r = await api.put<{ control: IntegrationControl }>(
        `/api/integrations/${encodeURIComponent(it.id)}/control`,
        {
          schedule: null,
          full_rebuild_cron: null,
        } satisfies IntegrationControlUpdate
      );
      updateControl(it.id, r.control);
      setEditing(null);
      toast(t.integrations.toasts.restored);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <BackLink to="/admin" />
      <PageHeader
        title={t.integrations.page.title}
        subtitle={t.integrations.page.subtitle}
        action={
          <Button
            variant="secondary"
            icon={<RefreshCw className="h-5 w-5" aria-hidden />}
            onClick={() => {
              setError(null);
              load();
            }}
          >
            {t.integrations.actions.refresh}
          </Button>
        }
        badge={
          items ? (
            <Badge tone="accent">{t.integrations.page.count(items.length)}</Badge>
          ) : null
        }
      />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {items === null ? (
        error ? null : (
          <div role="status" className="flex justify-center py-12 text-accent">
            <Spinner className="h-8 w-8" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        )
      ) : items.length === 0 ? (
        <EmptyState icon={<Workflow className="h-7 w-7" aria-hidden />} title={t.integrations.page.emptyTitle}>
          {t.integrations.page.emptyText}
        </EmptyState>
      ) : (
        <ul className="space-y-4">
          {items.map((it) => {
            const control = it.control;
            const stateRunning = it.running_run_id !== null;
            const freqWords = frequencyWords(control.schedule, control.schedule_words);
            const freqDescribed =
              control.schedule_words !== null || describeCron(control.schedule) !== null;
            const fullRebuildWords = control.full_rebuild_crons.map((c) => frequencyWords(c)).join(", ");
            const fullOutside = fullRebuildOutsideWindow(control.full_rebuild_crons, control.window);
            return (
              <li key={it.id}>
                <Card className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                        <Workflow className="h-5 w-5" aria-hidden />
                      </span>
                      <div className="min-w-0">
                        <h2 className="font-semibold text-ink [overflow-wrap:anywhere]">{it.id}</h2>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5">
                          <CodeChip>{it.source}</CodeChip>
                          <span className="text-sm text-ink-muted [overflow-wrap:anywhere]">
                            {it.datasets.join(", ")}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {stateRunning ? (
                        <Badge tone="blue" icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden />}>
                          {t.integrations.state.running}
                        </Badge>
                      ) : null}
                      {control.paused ? (
                        <Badge tone="amber" icon={<Pause className="h-3.5 w-3.5" aria-hidden />}>
                          {t.integrations.state.paused}
                        </Badge>
                      ) : null}
                      {!stateRunning && !control.paused ? (
                        <Badge tone="green" icon={<CheckCircle2 className="h-3.5 w-3.5" aria-hidden />}>
                          {t.integrations.state.active}
                        </Badge>
                      ) : null}
                      {it.paused ? <Badge tone="amber">{t.integrations.labels.sourceDisabled}</Badge> : null}
                      <RunStatus run={it.last_run} />
                    </div>
                  </div>

                  <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <div className="rounded-xl bg-subtle px-3 py-2">
                      <dt className="text-xs font-medium text-ink-muted">{t.integrations.labels.frequency}</dt>
                      <dd className="mt-0.5 text-sm font-semibold text-ink">
                        {freqDescribed ? (
                          freqWords
                        ) : (
                          <CodeChip>{control.schedule}</CodeChip>
                        )}{" "}
                        <span className="font-normal text-ink-muted">
                          {t.integrations.source[control.schedule_source]}
                        </span>
                      </dd>
                    </div>
                    <div className="rounded-xl bg-subtle px-3 py-2">
                      <dt className="text-xs font-medium text-ink-muted">{t.integrations.labels.window}</dt>
                      <dd className="mt-0.5 text-sm font-semibold text-ink">
                        {control.window
                          ? t.integrations.labels.windowRange(control.window.start, control.window.end)
                          : t.integrations.labels.allDay}
                      </dd>
                    </div>
                    <div className="rounded-xl bg-subtle px-3 py-2">
                      <dt className="text-xs font-medium text-ink-muted">{t.integrations.labels.nextRun}</dt>
                      <dd className="mt-0.5 text-sm font-semibold text-ink">
                        {formatDateTime(control.next_run)}
                      </dd>
                    </div>
                    <div className="rounded-xl bg-subtle px-3 py-2">
                      <dt className="text-xs font-medium text-ink-muted">{t.integrations.labels.fullRebuild}</dt>
                      <dd className="mt-0.5 text-sm font-semibold text-ink">
                        {control.full_rebuild_crons.length > 0 ? (
                          <>
                            {fullRebuildWords}{" "}
                            <span className="font-normal text-ink-muted">
                              {t.integrations.source[control.full_rebuild_source]}
                            </span>
                          </>
                        ) : (
                          t.integrations.labels.noFullRebuild
                        )}
                      </dd>
                    </div>
                    <div className="rounded-xl bg-subtle px-3 py-2">
                      <dt className="text-xs font-medium text-ink-muted">{t.integrations.labels.lastSuccess}</dt>
                      <dd className="mt-0.5 text-sm font-semibold text-ink">
                        {formatDateTime(it.last_success_at)}
                      </dd>
                    </div>
                  </dl>

                  {fullOutside !== null ? (
                    <p className="mt-3 flex items-start gap-2 text-sm text-warning-deep">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                      {t.integrations.labels.fullRebuildOutsideWindow(fullOutside)}
                    </p>
                  ) : null}

                  {it.last_run?.message ? (
                    <p className="mt-3 text-sm text-danger-strong [overflow-wrap:anywhere]">
                      {it.last_run.message}
                    </p>
                  ) : null}

                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      loading={busy === `${it.id}:incremental`}
                      icon={<Play className="h-5 w-5" aria-hidden />}
                      onClick={() => run(it.id, "incremental")}
                    >
                      {t.integrations.actions.runNow}
                    </Button>
                    <Button
                      variant="secondary"
                      loading={busy === `${it.id}:full`}
                      onClick={() => run(it.id, "full")}
                    >
                      {t.integrations.actions.fullRun}
                    </Button>
                    <Button
                      variant="secondary"
                      loading={busy === `${it.id}:pause`}
                      icon={
                        control.paused ? (
                          <PlayCircle className="h-5 w-5" aria-hidden />
                        ) : (
                          <Pause className="h-5 w-5" aria-hidden />
                        )
                      }
                      onClick={() => togglePaused(it)}
                    >
                      {control.paused ? t.integrations.actions.resume : t.integrations.actions.pause}
                    </Button>
                    {stateRunning ? (
                      <Button
                        variant="danger"
                        loading={busy === `${it.id}:stop`}
                        icon={<Square className="h-5 w-5" aria-hidden />}
                        onClick={() => stopRun(it)}
                      >
                        {t.integrations.actions.stop}
                      </Button>
                    ) : null}
                    <Button
                      variant="secondary"
                      icon={<CalendarClock className="h-5 w-5" aria-hidden />}
                      onClick={() => setEditing(it)}
                    >
                      {t.integrations.actions.changeFrequency}
                    </Button>
                    <IconButton
                      aria-label={t.integrations.actions.history}
                      aria-expanded={open === it.id}
                      icon={
                        <ChevronDown
                          className={`h-5 w-5 transition-transform ${open === it.id ? "rotate-180" : ""}`}
                          aria-hidden
                        />
                      }
                      onClick={() => setOpen(open === it.id ? null : it.id)}
                    />
                  </div>

                  {open === it.id ? (
                    <div className="mt-3 border-t border-line pt-3">
                      <Runs id={it.id} />
                    </div>
                  ) : null}
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      <View
        open={editing !== null}
        title={editing ? t.integrations.form.title(editing.id) : ""}
        onClose={() => setEditing(null)}
        autoFocus={false}
      >
        {editing ? (
          <FrequencyForm
            key={editing.id}
            integration={editing}
            busy={busy === `${editing.id}:save` || busy === `${editing.id}:restore`}
            onSubmit={(body) => submitControl(editing, body)}
            onRestore={() => restoreSpec(editing)}
            onCancel={() => setEditing(null)}
          />
        ) : null}
      </View>
    </div>
  );
}
