import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import { Ban, ExternalLink, Link2, Pencil, RefreshCw, RotateCw, X } from "lucide-react";
import { api, ApiError } from "../../api/client";
import type { CreatedWidget, DashboardWidget, WidgetsState } from "../../api/types";
import { useT } from "../../i18n";
import { holdSnippet } from "../../lib/widgetSnippet";
import { formatDateTime } from "../../lib/format";
import { errorText } from "../../lib/sharing";
import { Alert } from "../Alert";
import { Badge } from "../Badge";
import { Button } from "../Button";
import { Card } from "../Card";
import { CopyButton } from "../CopyButton";
import { EmptyState } from "../EmptyState";
import { Input } from "../Input";
import { Select } from "../Select";
import { Spinner } from "../Spinner";
import { Switch } from "../Switch";
import { useToast } from "../Toast";

interface FormValues {
  name: string;
  sites: string;
  theme: "" | "light" | "dark";
  language: "" | "es" | "en";
  showTitle: boolean;
  showFilters: boolean;
  pdf: boolean;
  expiresAt: string;
}

const EMPTY: FormValues = {
  name: "",
  sites: "",
  theme: "",
  language: "",
  showTitle: true,
  showFilters: true,
  pdf: false,
  expiresAt: "",
};

function valuesOf(widget: DashboardWidget): FormValues {
  return {
    name: widget.name,
    sites: widget.sites.map((site) => site.origin).join("\n"),
    theme: widget.theme ?? "",
    language: widget.language ?? "",
    showTitle: widget.show_title,
    showFilters: widget.show_filters,
    pdf: widget.pdf,
    expiresAt: widget.expires_at ? widget.expires_at.slice(0, 10) : "",
  };
}

/** The chosen day, end of day local, as the instant the API stores. */
function expiryPayload(date: string): string | null {
  if (!date) return null;
  const moment = new Date(`${date}T23:59:59`);
  return Number.isNaN(moment.getTime()) ? null : moment.toISOString();
}

function statusBadge(widget: DashboardWidget, t: ReturnType<typeof useT>) {
  if (widget.state === "revoked") return <Badge tone="gray">{t.sharing.statusRevoked}</Badge>;
  if (widget.state === "expired") return <Badge tone="amber">{t.sharing.statusExpired}</Badge>;
  return <Badge tone="green">{t.sharing.statusActive}</Badge>;
}

function Sites({ widget }: { widget: DashboardWidget }) {
  const t = useT();
  if (widget.sites.length === 0) return <span className="text-sm text-ink-soft">—</span>;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {widget.sites.map((site) => (
        <Badge key={site.origin} tone={site.development ? "amber" : "blue"} wrap>
          <span className="mr-1 break-all font-mono text-xs">{site.origin}</span>
          {site.development ? (
            <span className="text-xs font-semibold">{t.widgets.development}</span>
          ) : null}
        </Badge>
      ))}
    </div>
  );
}

function Form({
  initial,
  maxSites,
  nameMax,
  busy,
  submitLabel,
  onSubmit,
  onCancel,
  error,
  fieldError,
}: {
  initial: FormValues;
  maxSites: number;
  nameMax: number;
  busy: boolean;
  submitLabel: string;
  onSubmit: (values: FormValues) => void;
  onCancel?: () => void;
  error?: string | null;
  fieldError?: string | null;
}) {
  const t = useT();
  const [values, setValues] = useState<FormValues>(initial);
  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) =>
    setValues((current) => ({ ...current, [key]: value }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(values);
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Input
        label={t.widgets.nameLabel}
        hint={t.widgets.nameHint}
        maxLength={nameMax}
        required
        value={values.name}
        onChange={(event) => set("name", event.target.value)}
        error={fieldError}
      />
      <div>
        <label htmlFor="widget-sites" className="mb-1.5 block text-sm font-semibold text-ink-2">
          {t.widgets.sitesLabel}
          <span aria-hidden="true" className="text-danger">*</span>
        </label>
        <textarea
          id="widget-sites"
          rows={3}
          value={values.sites}
          onChange={(event) => set("sites", event.target.value)}
          placeholder={t.widgets.sitesPlaceholder}
          className="block w-full rounded-xl border border-transparent bg-field px-4 py-3 font-mono text-sm text-ink placeholder-ink-faint focus:outline-none focus:ring-2 focus:ring-field-focus"
        />
        <p className="mt-1.5 text-sm text-ink-soft">{t.widgets.sitesHint(maxSites)}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Select
          label={t.widgets.themeLabel}
          value={values.theme}
          onChange={(event) => set("theme", event.target.value as FormValues["theme"])}
        >
          <option value="">{t.widgets.themeAuto}</option>
          <option value="light">{t.sharing.themeLight}</option>
          <option value="dark">{t.sharing.themeDark}</option>
        </Select>
        <Select
          label={t.widgets.languageLabel}
          value={values.language}
          onChange={(event) => set("language", event.target.value as FormValues["language"])}
        >
          <option value="">{t.widgets.languageAuto}</option>
          <option value="es">Español</option>
          <option value="en">English</option>
        </Select>
      </div>

      <Input
        label={t.widgets.expiryLabel}
        hint={t.widgets.expiryHint}
        type="date"
        value={values.expiresAt}
        onChange={(event) => set("expiresAt", event.target.value)}
      />

      <div className="space-y-2">
        <Toggle
          checked={values.showTitle}
          onChange={(v) => set("showTitle", v)}
          label={t.widgets.titleLabel}
        />
        <Toggle
          checked={values.showFilters}
          onChange={(v) => set("showFilters", v)}
          label={t.widgets.filtersLabel}
        />
        <Toggle checked={values.pdf} onChange={(v) => set("pdf", v)} label={t.widgets.pdfLabel} />
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" icon={<Link2 className="h-5 w-5" aria-hidden />}
                loading={busy}>
          {submitLabel}
        </Button>
        {onCancel ? (
          <Button variant="secondary" icon={<X className="h-5 w-5" aria-hidden />} onClick={onCancel}>
            {t.common.cancel}
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <div className="flex min-h-tap items-center justify-between gap-3">
      <span className="text-sm font-semibold text-ink-2">{label}</span>
      <Switch checked={checked} onChange={onChange} label={label} />
    </div>
  );
}

function Snippet({ widget, title, hint }: { widget: CreatedWidget; title: string; hint: string }) {
  return (
    <Alert tone="success">
      <div className="space-y-2">
        <p className="text-sm font-semibold">{title}</p>
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-subtle px-3 py-2 text-xs text-ink">
          {widget.snippet}
        </pre>
        <div className="flex flex-wrap items-center gap-2">
          <CopyButton text={widget.snippet} />
          <code className="break-all text-xs text-ink-2">{widget.url}</code>
        </div>
        <p className="text-xs text-ink-soft">{hint}</p>
      </div>
    </Alert>
  );
}

/** Feature 065: the widgets of one dashboard, created and managed from its sharing screen. */
export function WidgetsPanel({ code }: { code: string }) {
  const t = useT();
  const toast = useToast();
  const [state, setState] = useState<WidgetsState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedWidget | null>(null);
  const [createdReplacement, setCreatedReplacement] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<number | null>(null);
  const [confirmReplace, setConfirmReplace] = useState<number | null>(null);

  const url = `/api/dashboards/${encodeURIComponent(code)}/widgets`;

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setState(await api.get<WidgetsState>(url));
    } catch (e) {
      setLoadError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    void load();
  }, [load]);

  const atMax = state ? state.active_count >= state.max_active : false;
  const disabledReason: ReactNode = useMemo(() => {
    if (!state) return null;
    if (!state.embed_enabled) return <Alert tone="info">{t.widgets.disabledInstall}</Alert>;
    if (!state.share_links_enabled) return <Alert tone="info">{t.widgets.disabledLinks}</Alert>;
    if (!state.shareable) return <Alert tone="warning">{t.widgets.notShareable}</Alert>;
    return null;
  }, [state, t]);

  const failure = (e: unknown) => {
    if (e instanceof ApiError) {
      if (e.status === 422 && e.fields.name) {
        setFieldError(e.message);
        return;
      }
      if (e.status === 422 || e.status === 409) {
        setError(e.message);
        return;
      }
    }
    setError(errorText(e));
  };

  const create = async (values: FormValues) => {
    setError(null);
    setFieldError(null);
    setBusy(true);
    try {
      const widget = await api.post<CreatedWidget>(url, {
        name: values.name.trim(),
        sites: values.sites.split(/\r?\n/).map((site) => site.trim()).filter(Boolean),
        theme: values.theme || null,
        language: values.language || null,
        show_title: values.showTitle,
        show_filters: values.showFilters,
        pdf: values.pdf,
        expires_at: expiryPayload(values.expiresAt),
      });
      setCreated(widget);
      setCreatedReplacement(false);
      // In memory only: the key must never reach browser storage (FR-002/FR-011).
      holdSnippet(code, widget.id, widget.snippet);
      await load();
    } catch (e) {
      failure(e);
    } finally {
      setBusy(false);
    }
  };

  const save = async (id: number, values: FormValues) => {
    setError(null);
    setFieldError(null);
    setBusy(true);
    try {
      await api.patch(url + `/${id}`, {
        name: values.name.trim(),
        sites: values.sites.split(/\r?\n/).map((site) => site.trim()).filter(Boolean),
        theme: values.theme || null,
        language: values.language || null,
        show_title: values.showTitle,
        show_filters: values.showFilters,
        pdf: values.pdf,
        expires_at: expiryPayload(values.expiresAt),
      });
      setEditing(null);
      await load();
    } catch (e) {
      failure(e);
    } finally {
      setBusy(false);
    }
  };

  const replace = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      const widget = await api.post<CreatedWidget>(url + `/${id}/replace`, {});
      setCreated(widget);
      setCreatedReplacement(true);
      holdSnippet(code, widget.id, widget.snippet);
      setConfirmReplace(null);
      await load();
    } catch (e) {
      failure(e);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      await api.del(url + `/${id}`);
      toast(t.widgets.revokedToast);
      setConfirmRevoke(null);
      setEditing(null);
      await load();
    } catch (e) {
      failure(e);
    } finally {
      setBusy(false);
    }
  };

  if (loading && !state) {
    return (
      <div role="status" className="flex justify-center py-8 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  if (loadError || !state) {
    return (
      <Alert
        tone="error"
        action={
          <Button variant="secondary" icon={<RefreshCw className="h-5 w-5" aria-hidden />}
                  onClick={() => void load()}>
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
      <p className="text-sm text-ink-2">{t.widgets.intro}</p>
      {/* FR-012: in plain words, before anything is created. */}
      <Alert tone="warning">{t.widgets.warning}</Alert>

      {state.enabled && state.shareable ? (
        <p className="text-sm font-semibold text-ink-2">
          {t.widgets.count(state.active_count, state.max_active)}
        </p>
      ) : null}

      {disabledReason}
      {atMax && state.enabled && state.shareable ? (
        <Alert tone="warning">{t.widgets.maxActive(state.max_active)}</Alert>
      ) : null}

      {created ? (
        <div className="space-y-2">
          <Snippet
            widget={created}
            title={createdReplacement ? t.widgets.replacedTitle : t.widgets.createdTitle}
            hint={t.widgets.snippetHint}
          />
          <Link
            to={`/d/${encodeURIComponent(code)}/widgets/${created.id}/probar`}
            className="inline-flex min-h-tap items-center gap-2 text-sm font-semibold text-accent underline-offset-2 hover:underline"
          >
            <ExternalLink className="h-4 w-4" aria-hidden />
            {t.widgets.test}
          </Link>
        </div>
      ) : null}

      {state.enabled && state.shareable && !atMax ? (
        <Card tone="accent" className="p-5">
          <Form
            key={state.items.length}
            initial={EMPTY}
            maxSites={state.max_sites}
            nameMax={state.name_max}
            busy={busy}
            submitLabel={t.widgets.create}
            onSubmit={(values) => void create(values)}
            error={error}
            fieldError={fieldError}
          />
        </Card>
      ) : null}

      <section>
        <h2 className="mb-3 text-base font-semibold text-ink">{t.widgets.listTitle}</h2>
        {state.items.length === 0 ? (
          <EmptyState title={t.widgets.noWidgets} />
        ) : (
          <Card className="p-0">
            <ul className="divide-y divide-line">
              {state.items.map((widget) => (
                <li key={widget.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-ink">{widget.name}</p>
                        {statusBadge(widget, t)}
                      </div>
                      <Sites widget={widget} />
                      <p className="text-sm text-ink-muted">
                        {t.widgets.meta(
                          widget.created_by.name ?? "—",
                          formatDateTime(widget.created_at),
                          widget.expires_at ? formatDateTime(widget.expires_at) : null,
                          widget.visits,
                          widget.last_visit_at ? formatDateTime(widget.last_visit_at) : null,
                        )}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {widget.active ? (
                        <Link
                          to={`/d/${encodeURIComponent(code)}/widgets/${widget.id}/probar`}
                          className="inline-flex min-h-tap items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-accent hover:bg-subtle"
                        >
                          <ExternalLink className="h-4 w-4" aria-hidden />
                          {t.widgets.test}
                        </Link>
                      ) : null}
                      {widget.active && editing !== widget.id ? (
                        <>
                          <Button
                            variant="secondary"
                            icon={<Pencil className="h-5 w-5" aria-hidden />}
                            onClick={() => {
                              setEditing(widget.id);
                              setError(null);
                              setFieldError(null);
                            }}
                          >
                            {t.widgets.edit}
                          </Button>
                          {confirmReplace === widget.id ? (
                            <>
                              <Button variant="danger" loading={busy}
                                      onClick={() => void replace(widget.id)}>
                                {t.widgets.replaceConfirm}
                              </Button>
                              <Button variant="secondary" onClick={() => setConfirmReplace(null)}>
                                {t.common.cancel}
                              </Button>
                            </>
                          ) : (
                            <Button
                              variant="secondary"
                              icon={<RotateCw className="h-5 w-5" aria-hidden />}
                              onClick={() => setConfirmReplace(widget.id)}
                            >
                              {t.widgets.replace}
                            </Button>
                          )}
                          {confirmRevoke === widget.id ? (
                            <>
                              <Button variant="danger" loading={busy}
                                      onClick={() => void revoke(widget.id)}>
                                {t.widgets.confirmRevoke}
                              </Button>
                              <Button variant="secondary" onClick={() => setConfirmRevoke(null)}>
                                {t.common.cancel}
                              </Button>
                            </>
                          ) : (
                            <Button
                              variant="secondary"
                              icon={<Ban className="h-5 w-5" aria-hidden />}
                              onClick={() => setConfirmRevoke(widget.id)}
                            >
                              {t.widgets.revoke}
                            </Button>
                          )}
                        </>
                      ) : null}
                    </div>
                  </div>
                  {editing === widget.id ? (
                    <div className="mt-4 rounded-xl bg-surface-2 p-4">
                      <Form
                        initial={valuesOf(widget)}
                        maxSites={state.max_sites}
                        nameMax={state.name_max}
                        busy={busy}
                        submitLabel={t.widgets.save}
                        onSubmit={(values) => void save(widget.id, values)}
                        onCancel={() => setEditing(null)}
                        error={error}
                        fieldError={fieldError}
                      />
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
