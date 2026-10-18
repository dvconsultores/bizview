import { AlertTriangle, Clock, Plus, Trash2, Zap } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { api, ApiError } from "../../api/client";
import type { DataSource, FieldDef, HeaderDef, SourceKind, SourceTest, SourceTypes } from "../../api/types";
import { Alert } from "../../components/Alert";
import { Breadcrumbs } from "../../components/Breadcrumbs";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Input } from "../../components/Input";
import { PageHeader } from "../../components/PageHeader";
import { PemField, SecretField } from "../../components/SecretField";
import { Select } from "../../components/Select";
import { Spinner } from "../../components/Spinner";
import { Switch } from "../../components/Switch";
import { useToast } from "../../components/Toast";
import { View } from "../../components/View";
import { useT } from "../../i18n";
import { KIND_ICONS } from "./Sources";

const LONG = new Set(["pem", "headers", "url"]);






type Secrets = Record<string, string | null | undefined>;
interface HeaderRow {
  key: number;
  name: string;
  secret: boolean;
  value: string | null | undefined; // secret headers: undefined keeps the stored value
  configured: boolean;
}

let headerKey = 0;

function defaultsFor(fields: FieldDef[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) if (!f.secret && f.type !== "headers" && f.default != null) out[f.name] = f.default;
  return out;
}

function visible(f: FieldDef, values: Record<string, unknown>, fields: FieldDef[]): boolean {
  return Object.keys(f.show_if).every((k) => {
    const def = fields.find((x) => x.name === k)?.default;
    return f.show_if[k].indexOf(String(values[k] ?? def ?? "")) !== -1;
  });
}

function headerRows(source: DataSource | null): HeaderRow[] {
  const list = ((source?.settings.headers as HeaderDef[] | undefined) ?? []);
  return list.map((h) => ({
    key: headerKey++,
    name: h.name,
    secret: h.secret,
    value: h.secret ? undefined : h.value ?? "",
    configured: h.secret && (source?.secret_fields ?? []).indexOf(`header:${h.name.toLowerCase()}`) !== -1,
  }));
}

export function SourceForm() {
  const t = useT();
  const T = t.admin.sourceForm;
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const [types, setTypes] = useState<SourceTypes | null>(null);
  const [source, setSource] = useState<DataSource | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [kind, setKind] = useState<SourceKind>("postgresql");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [directReports, setDirectReports] = useState(false);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [secrets, setSecrets] = useState<Secrets>({});
  const [headers, setHeaders] = useState<HeaderRow[]>([]);
  const [dirty, setDirty] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<SourceTest | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const load = (src: DataSource | null, ty: SourceTypes) => {
    setSource(src);
    // A fuente spec links here with ?kind=<kind> (feature 020): preselect it for a new source.
    const requested = new URLSearchParams(location.search).get("kind");
    const k = src?.kind ?? (requested && requested in ty ? (requested as SourceKind) : "postgresql");
    setKind(k);
    setName(src?.name ?? "");
    setDescription(src?.description ?? "");
    setEnabled(src?.enabled ?? true);
    setDirectReports(src?.direct_reports ?? false);
    setValues(src ? { ...src.settings } : defaultsFor(ty[k].fields));
    setSecrets({});
    setHeaders(headerRows(src));
    setDirty(false);
    setErrors({});
  };

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    Promise.all([api.get<SourceTypes>("/api/sources/types"), id ? api.get<DataSource>(`/api/sources/${id}`) : Promise.resolve(null)])
      .then(([ty, src]) => {
        if (cancelled) return;
        setTypes(ty);
        load(src, ty);
      })
      .catch((err) => !cancelled && setLoadError(err instanceof ApiError ? err.message : t.common.unexpected));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (deleted && !((location.state as { view?: string[] } | null)?.view?.length)) {
      navigate("/admin/fuentes", { replace: true });
    }
  }, [deleted, location.state, navigate]);

  const fields = useMemo(() => (types ? types[kind].fields : []), [types, kind]);
  const shown = fields.filter((f) => visible(f, values, fields));
  const touch = () => {
    setDirty(true);
    setResult(null);
  };
  const setValue = (k: string, v: unknown) => {
    setValues((prev) => ({ ...prev, [k]: v }));
    touch();
  };

  const body = () => {
    const settings: Record<string, unknown> = {};
    for (const f of shown) {
      if (f.secret) continue;
      if (f.type === "headers") {
        settings.headers = headers
          .filter((h) => h.name.trim())
          .map((h) => {
            const out: HeaderDef = { name: h.name.trim(), secret: h.secret };
            if (!h.secret || typeof h.value === "string") out.value = h.value ?? "";
            return out;
          });
        continue;
      }
      const v = values[f.name];
      if (v === undefined || v === null || v === "") continue;
      settings[f.name] = f.type === "integer" ? Number(v) : v;
    }
    const sec: Record<string, string | null> = {};
    for (const f of shown) if (f.secret && secrets[f.name] !== undefined) sec[f.name] = secrets[f.name] as string | null;
    return { name: name.trim(), kind, description: description.trim(), enabled,
             direct_reports: kind === "postgresql" ? directReports : false,
             settings, secrets: sec };
  };

  const showErrors = (err: unknown) => {
    if (err instanceof ApiError && err.status === 409) setErrors({ name: T.conflict });
    else if (err instanceof ApiError && err.code === "validation_error") {
      const mapped: Record<string, string> = {};
      for (const [k, code] of Object.entries(err.fields)) mapped[k] = T.errors[code] ?? err.message;
      setErrors(mapped);
      setFormError(Object.keys(mapped).some((k) => k === "kind" || k === "_") ? err.message : null);
    } else setFormError(err instanceof ApiError ? err.message : t.common.unexpected);
  };

  const runTest = async () => {
    setTesting(true);
    setResult(null);
    setErrors({});
    setFormError(null);
    try {
      const b = body();
      const res = source
        ? await api.post<SourceTest>(`/api/sources/${source.id}/test`, dirty ? { settings: b.settings, secrets: b.secrets } : {})
        : await api.post<SourceTest>("/api/sources/test", b);
      setResult(res);
    } catch (err) {
      showErrors(err);
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setErrors({});
    setFormError(null);
    try {
      const b = body();
      if (source) {
        const { kind: _kind, ...patch } = b;
        const updated = await api.patch<DataSource>(`/api/sources/${source.id}`, patch);
        toast(T.saved);
        if (types) load(updated, types);
      } else {
        const created = await api.post<DataSource>("/api/sources", b);
        toast(T.created);
        navigate(`/admin/fuentes/${created.id}`, { replace: true });
      }
    } catch (err) {
      showErrors(err);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!source) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.del(`/api/sources/${source.id}`);
      toast(T.deleted);
      setDeleted(true);
      setConfirmDelete(false);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setDeleting(false);
    }
  };

  if (loadError) {
    return (
      <div className="space-y-5">
        <Breadcrumbs back="/admin/fuentes" items={[]} />
        <Alert tone="error">{loadError}</Alert>
      </div>
    );
  }
  if (!types) {
    return (
      <div role="status" className="flex justify-center py-12 text-accent">
        <Spinner className="h-8 w-8" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  const field = (f: FieldDef): ReactNode => {
    const err = errors[`${f.secret ? "secrets" : "settings"}.${f.name}`];
    if (f.secret) {
      return (
        <SecretField key={f.name} field={f} configured={(source?.secret_fields ?? []).indexOf(f.name) !== -1}
          value={secrets[f.name]} error={err}
          onChange={(v) => { setSecrets((p) => ({ ...p, [f.name]: v })); touch(); }} />
      );
    }
    if (f.type === "enum") {
      return (
        <Select key={f.name} id={`f-${f.name}`} label={f.label} required={f.required} error={err}
          hint={f.help || undefined} value={String(values[f.name] ?? f.default ?? "")}
          onChange={(e) => setValue(f.name, e.target.value)}>
          {f.options.map((o) => <option key={o} value={o}>{T.options[o] ?? o}</option>)}
        </Select>
      );
    }
    if (f.type === "pem") {
      return (
        <PemField
          key={f.name}
          id={`f-${f.name}`}
          label={f.label}
          required={f.required}
          value={String(values[f.name] ?? "")}
          onChange={(v) => setValue(f.name, v)}
          error={err}
          help={f.help || undefined}
        />
      );
    }
    if (f.type === "headers") {
      const headerErr = errors["settings.headers"];
      return (
        <fieldset key={f.name} className="space-y-3">
          <legend className="mb-1.5 text-sm font-semibold text-ink-2">{f.label}</legend>
          {headers.map((h, i) => {
            const update = (patch: Partial<HeaderRow>) => {
              setHeaders((p) => p.map((x, j) => (j === i ? { ...x, ...patch } : x)));
              touch();
            };
            return (
              <div key={h.key} className="space-y-3 rounded-xl border border-line p-3">
                <div className="flex items-end">
                  <Input className="min-w-0 flex-1" label={T.headerName} value={h.name} autoCapitalize="none"
                    spellCheck={false} onChange={(e) => update({ name: e.target.value })} />
                  <button type="button" aria-label={T.removeHeader}
                    onClick={() => { setHeaders((p) => p.filter((_, j) => j !== i)); touch(); }}
                    className="ml-2 inline-flex min-h-tap min-w-tap items-center justify-center rounded-lg text-ink-soft hover:bg-danger-soft hover:text-danger">
                    <Trash2 className="h-5 w-5" aria-hidden />
                  </button>
                </div>
                {h.secret ? (
                  <SecretField field={{ name: `header-${h.key}`, label: T.headerValue, type: "string", required: false, help: "" }}
                    configured={h.configured} value={h.value} onChange={(v) => update({ value: v ?? undefined })} />
                ) : (
                  <Input label={T.headerValue} value={h.value ?? ""} spellCheck={false}
                    onChange={(e) => update({ value: e.target.value })} />
                )}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-ink-3">{T.headerSecret}</span>
                  <Switch checked={h.secret} label={`${T.headerSecret}: ${h.name || T.headerName}`}
                    onChange={(v) => update({ secret: v, value: v ? "" : "", configured: false })} />
                </div>
              </div>
            );
          })}
          {headerErr ? <p className="text-sm text-danger">{headerErr}</p> : null}
          {headers.length < 20 ? (
            <Button variant="ghost" icon={<Plus className="h-5 w-5" aria-hidden />}
              onClick={() => { setHeaders((p) => [...p, { key: headerKey++, name: "", secret: false, value: "", configured: false }]); touch(); }}>
              {T.addHeader}
            </Button>
          ) : null}
        </fieldset>
      );
    }
    return (
      <Input key={f.name} label={f.label} required={f.required} error={err} hint={f.help || undefined}
        type={f.type === "integer" ? "number" : f.type === "url" ? "url" : "text"}
        inputMode={f.type === "integer" ? "numeric" : f.type === "url" ? "url" : undefined}
        placeholder={f.type === "url" ? "https://…" : undefined}
        min={f.min ?? undefined} max={f.max ?? undefined}
        autoCapitalize="none" spellCheck={false}
        value={values[f.name] == null ? "" : String(values[f.name])}
        onChange={(e) => setValue(f.name, e.target.value)} />
    );
  };

  const details = result?.details ?? {};
  const services = (details.services as { name: string; ports: { name: string; operations: string[] }[] }[] | undefined) ?? [];

  return (
    <div className="space-y-5 pb-28 lg:pb-0">
      <Breadcrumbs back="/admin/fuentes" items={[{ label: t.nav.admin, to: "/admin" }, { label: t.admin.sources.title, to: "/admin/fuentes" }, { label: source ? source.name : T.newTitle }]} />
      <PageHeader title={source ? source.name : T.newTitle} subtitle={source ? types[source.kind].label : undefined} />
      {source?.imported ? <Alert tone="warning">{T.imported}</Alert> : null}
      {formError ? <Alert tone="error">{formError}</Alert> : null}

      <Card tone="accent" className="space-y-4 p-5 sm:p-6">
        {!source ? (
          <fieldset>
            <legend className="mb-1.5 text-sm font-semibold text-ink-2">{T.kind}</legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {(Object.keys(types) as SourceKind[]).map((k) => {
                const Icon = KIND_ICONS[k];
                const selected = kind === k;
                return (
                  <label key={k} className={`flex min-h-tap cursor-pointer items-center rounded-xl border p-3 focus-within:ring-2 focus-within:ring-accent-line-strong ${
                    selected ? "border-primary bg-accent-soft ring-1 ring-primary" : "border-line-strong bg-surface hover:border-accent-line-strong"}`}>
                    <input type="radio" name="kind" value={k} checked={selected} className="sr-only"
                      onChange={() => { setKind(k); setValues(defaultsFor(types[k].fields)); setSecrets({}); setHeaders([]); setDirectReports(false); touch(); }} />
                    <Icon className={`mr-2 h-5 w-5 ${selected ? "text-accent" : "text-ink-soft"}`} aria-hidden />
                    <span className="font-medium text-ink">{types[k].label}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        ) : (
          <p className="flex flex-wrap items-center text-sm text-ink-soft">
            <span className="mr-2"><Badge tone="blue">{types[source.kind].label}</Badge></span>
            {T.kindLocked}
          </p>
        )}
        <Input label={T.name} required value={name} error={errors.name} maxLength={80}
          onChange={(e) => { setName(e.target.value); touch(); }} />
        <Input label={T.description} value={description} maxLength={300}
          onChange={(e) => { setDescription(e.target.value); touch(); }} />
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-ink-2">{T.enabled}</span>
          <Switch checked={enabled} label={T.enabled} onChange={(v) => { setEnabled(v); touch(); }} />
        </div>
        {kind === "postgresql" ? (
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span id="direct-reports-label" className="text-sm font-semibold text-ink-2">{t.directSources.flag}</span>
              <Switch checked={directReports} label={t.directSources.flag} onChange={(v) => { setDirectReports(v); touch(); }} />
            </div>
            <p className="text-sm text-ink-soft">{t.directSources.help}</p>
            {errors.direct_reports ? <p className="text-sm text-danger">{errors.direct_reports}</p> : null}
          </div>
        ) : null}
      </Card>

      <Card className="space-y-4 p-5 sm:p-6">
        <h2 className="text-lg font-semibold text-ink">{T.connection}</h2>
        {!types[kind].http_allowed ? <Alert tone="info">{T.httpsOnly}</Alert> : null}
        <div className="space-y-4 xl:grid xl:grid-cols-2 xl:gap-5 xl:space-y-0">
          {shown.map((f) => (
            <div key={f.name} className={LONG.has(f.type) ? "xl:col-span-2" : undefined}>
              {field(f)}
            </div>
          ))}
        </div>
      </Card>

      {result ? (
        <Card className="space-y-3 p-5 sm:p-6" aria-live="polite">
          {result.ok ? <Alert tone="success">{T.ok}</Alert> : <Alert tone="error">{result.message}</Alert>}
          {result.latency_ms != null ? (
            <p className="flex items-center text-sm text-ink-muted"><Clock className="mr-1.5 h-4 w-4" aria-hidden />{T.latency(result.latency_ms)}</p>
          ) : null}
          {result.warning_messages.map((w) => (
            <Alert key={w} tone="warning">{w}</Alert>
          ))}
          {Object.keys(details).length ? (
            <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
              {details.server_version ? (<div><dt className="text-ink-soft">{T.serverVersion}</dt><dd className="break-words font-medium">{String(details.server_version)}</dd></div>) : null}
              {details.status != null ? (<div><dt className="text-ink-soft">{T.status}</dt><dd className="font-medium">{String(details.status)} {String(details.content_type ?? "")}</dd></div>) : null}
              {details.bytes != null ? (<div><dt className="text-ink-soft">{T.bytes}</dt><dd className="font-medium">{String(details.bytes)} B</dd></div>) : null}
            </dl>
          ) : null}
          {services.length ? (
            <details className="text-sm">
              <summary className="min-h-tap cursor-pointer py-2 font-medium text-accent">{T.services}</summary>
              <ul className="space-y-2">
                {services.map((s) => (
                  <li key={s.name} className="break-words">
                    <p className="font-semibold">{s.name}</p>
                    {s.ports.map((p) => (
                      <p key={p.name} className="text-ink-muted">{p.name}: {p.operations.join(", ")}</p>
                    ))}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </Card>
      ) : null}

      <div className="sticky bottom-20 z-10 -mx-4 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur lg:static lg:mx-0 lg:border-0 lg:bg-transparent lg:px-0">
        {source && dirty ? <p className="mb-2 flex items-center text-xs text-ink-soft"><AlertTriangle className="mr-1 h-3.5 w-3.5" aria-hidden />{T.unsavedTest}</p> : null}
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end">
          {source ? (
            <Button variant="ghost" className="mt-2 text-danger hover:bg-danger-soft sm:mr-auto sm:mt-0" icon={<Trash2 className="h-5 w-5" aria-hidden />}
              onClick={() => { setDeleteError(null); setConfirmDelete(true); }}>{T.delete}</Button>
          ) : null}
          <Button variant="secondary" className="mt-2 sm:mr-2 sm:mt-0" icon={<Zap className="h-5 w-5" aria-hidden />} loading={testing} onClick={runTest}>
            {testing ? T.testing : T.test}
          </Button>
          <Button loading={saving} disabled={!!source && !dirty} onClick={save}>{T.save}</Button>
        </div>
      </div>

      <View open={confirmDelete} title={T.delete} onClose={() => { setConfirmDelete(false); setDeleteError(null); }}
        footer={
          <>
            <Button variant="secondary" onClick={() => { setConfirmDelete(false); setDeleteError(null); }}>{t.common.cancel}</Button>
            <Button variant="danger" loading={deleting} onClick={remove}>{T.delete}</Button>
          </>
        }>
        <div className="space-y-3">
          {deleteError ? <Alert tone="error">{deleteError}</Alert> : null}
          <p>{T.deleteBody}</p>
        </div>
      </View>
    </div>
  );
}
