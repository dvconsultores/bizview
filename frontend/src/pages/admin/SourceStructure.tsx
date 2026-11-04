import { AlertTriangle, ChevronRight, Download, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/client";
import { sourcesApi } from "../../api/sources";
import type {
  DataSource, SampleRequest, StructurePack, StructureTable,
} from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Input } from "../../components/Input";
import { Spinner } from "../../components/Spinner";
import { StructureChat } from "../../components/StructureChat";
import { useToast } from "../../components/Toast";
import { useT } from "../../i18n";
import { SPLIT_ASIDE } from "../../lib/layout";

/**
 * Feature 052: the Estructura tab.
 *
 * Shows what the source holds (structure only), downloads it in the authoring pack's format and
 * hosts the read-only structure chat beside it. Designed at 375 px first: one column, the chat as a
 * sheet; two panes from `lg`.
 */
const KIND_LABEL: Record<string, "table" | "view" | "materializedView" | "foreignTable"> = {
  table: "table",
  view: "view",
  materialized_view: "materializedView",
  foreign_table: "foreignTable",
};

function matches(table: StructureTable, kind: string | undefined, q: string) {
  if (!q) return true;
  const needle = q.toLowerCase();
  const columns = (table.columns ?? []).map((c) => c.name).join(" ");
  return [table.name, table.schema, kind, columns]
    .some((value) => (value ?? "").toLowerCase().includes(needle));
}

function ColumnRow({ sourceName, schema, table, column, onChanged, onError }:
  { sourceName: string; schema: string; table: string;
    column: StructureTable["columns"][number];
    onChanged: () => void; onError: (message: string) => void }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    setBusy(true);
    try {
      await sourcesApi.setPersonal(sourceName, {
        schema_name: schema, table, column: column.name, personal: !column.personal,
      });
      onChanged();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className="border-t border-line">
      <td className="break-words py-2 pr-3 font-medium text-ink">{column.name}</td>
      <td className="break-words py-2 pr-3 text-ink-muted">{column.type}</td>
      <td className="py-2 pr-3 text-ink-muted">{column.nullable ? T.nullable : "—"}</td>
      <td className="py-2 pr-3 text-ink-muted">
        {column.range ? T.dates(column.range.min ?? "…", column.range.max ?? "…") : "—"}
      </td>
      <td className="py-2">
        <button
          type="button"
          disabled={busy}
          onClick={toggle}
          aria-pressed={!!column.personal}
          title={T.personalHelp}
          className={`inline-flex min-h-tap items-center rounded-full px-2 py-1 text-xs font-semibold ${
            column.personal ? "bg-warning-soft text-warning" : "text-ink-soft hover:bg-surface-2"
          }`}
        >
          {column.personal ? T.personalChip : T.personal}
        </button>
      </td>
    </tr>
  );
}

function PostgresStructure({ pack, sourceName, query, onChanged, onError }:
  { pack: StructurePack; sourceName: string; query: string;
    onChanged: () => void; onError: (message: string) => void }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const tables = pack.structure.tables ?? [];
  const bySchema = useMemo(() => {
    const out = new Map<string, StructureTable[]>();
    for (const table of tables) {
      const schema = table.schema ?? "public";
      if (!out.has(schema)) out.set(schema, []);
      out.get(schema)!.push(table);
    }
    return [...out.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [tables]);

  if (!tables.length) return <p className="text-sm text-ink-soft">{T.noTables}</p>;
  let shown = 0;
  return (
    <div className="space-y-5">
      {bySchema.map(([schema, items]) => {
        const visible = items.filter((table) => matches(table, table.kind, query));
        shown += visible.length;
        if (!visible.length) return null;
        return (
          <section key={schema} className="space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">
              {T.schema} <span className="text-ink">{schema}</span>
            </h3>
            <ul className="space-y-2">
              {visible.map((table) => (
                <li key={`${schema}.${table.name}`}>
                  <details className="rounded-card border border-line bg-surface">
                    <summary className="flex min-h-tap cursor-pointer items-center px-3 py-2">
                      <ChevronRight className="mr-1.5 h-4 w-4 shrink-0 text-ink-soft" aria-hidden />
                      <span className="min-w-0 flex-1 break-words font-medium text-ink">
                        {table.name}
                      </span>
                      <span className="ml-2 flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                        <Badge tone="gray">{T[KIND_LABEL[table.kind ?? "table"] ?? "table"]}</Badge>
                        {table.estimated_rows != null ? (
                          <span className="text-xs text-ink-muted">
                            {T.rows(table.estimated_rows)}
                          </span>
                        ) : null}
                        <span className="text-xs text-ink-muted">
                          {T.columns(table.columns.length)}
                        </span>
                      </span>
                    </summary>
                    <div className="overflow-x-auto px-3 pb-3">
                      <table className="w-full min-w-[34rem] text-left text-sm">
                        <thead className="text-xs uppercase tracking-wide text-ink-soft">
                          <tr>
                            <th className="py-1 pr-3 font-semibold">{T.column}</th>
                            <th className="py-1 pr-3 font-semibold">{T.type}</th>
                            <th className="py-1 pr-3 font-semibold">{T.nullable}</th>
                            <th className="py-1 pr-3 font-semibold">{T.dateRange}</th>
                            <th className="py-1 font-semibold">{T.personal}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {table.columns.map((column) => (
                            <ColumnRow key={column.name} sourceName={sourceName} schema={schema}
                                       table={table.name} column={column}
                                       onChanged={onChanged} onError={onError} />
                          ))}
                        </tbody>
                      </table>
                      {table.primary_key?.length ? (
                        <p className="mt-2 text-xs text-ink-muted">
                          {T.key}: <code>{table.primary_key.join(", ")}</code>
                        </p>
                      ) : null}
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {!shown && query ? <p className="text-sm text-ink-soft">{T.searchEmpty(query)}</p> : null}
    </div>
  );
}

function SampleCard({ sample, onRun, onDelete }:
  { sample: SampleRequest; onRun: () => Promise<void>; onDelete: () => Promise<void> }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const [busy, setBusy] = useState(false);
  const suggestions = (sample.last_suggestions ?? {}) as Record<string, unknown>;
  const fields = (suggestions.fields ?? {}) as Record<string, string>;
  const units = suggestions.timestamp_units as string | null | undefined;
  const pagination = suggestions.pagination as string | null | undefined;

  return (
    <li className="rounded-card border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 break-words font-medium text-ink">{sample.name}</span>
        <Badge tone="blue">{sample.method}</Badge>
        <Button variant="ghost" size="sm" onClick={() => void onDelete()}
                aria-label={`${T.sampleDelete}: ${sample.name}`}>
          <Trash2 className="h-4 w-4" aria-hidden />
        </Button>
      </div>
      <p className="mt-1 break-words text-sm text-ink-muted">
        <code>{sample.path}</code>
        {Object.keys(sample.params ?? {}).length
          ? ` · ${Object.entries(sample.params).map(([k, v]) => `${k}=${v}`).join(", ")}` : ""}
      </p>
      {sample.last_error ? <Alert tone="error">{sample.last_error}</Alert> : null}
      {suggestions.records ? (
        <dl className="mt-2 grid grid-cols-1 gap-1 text-xs text-ink-muted sm:grid-cols-2">
          <div><dt className="inline font-semibold">{T.sampleRecords}: </dt>
            <dd className="inline"><code>{String(suggestions.records)}</code></dd></div>
          {Object.keys(fields).length ? (
            <div><dt className="inline font-semibold">{T.sampleFields}: </dt>
              <dd className="inline"><code>{Object.keys(fields).join(", ")}</code></dd></div>
          ) : null}
          {units ? <div><dt className="inline font-semibold">{T.sampleUnits}: </dt>
            <dd className="inline">{units}</dd></div> : null}
          {pagination ? <div><dt className="inline font-semibold">{T.samplePagination}: </dt>
            <dd className="inline">{pagination}</dd></div> : null}
        </dl>
      ) : (
        <p className="mt-2 text-xs text-ink-muted">{T.sampleNone}</p>
      )}
      <Button variant="secondary" size="sm" className="mt-2" loading={busy}
              onClick={async () => {
                setBusy(true);
                try { await onRun(); } finally { setBusy(false); }
              }}>
        {busy ? T.sampleRunning : T.sampleRun}
      </Button>
    </li>
  );
}

function RestSamples({ sourceName, samples, onChanged, onError }:
  { sourceName: string; samples: SampleRequest[]; onChanged: () => Promise<void>;
    onError: (message: string) => void }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [params, setParams] = useState("");
  const [adding, setAdding] = useState(false);

  const add = async () => {
    const pairs: Record<string, string> = {};
    for (const part of params.split(",").map((p) => p.trim()).filter(Boolean)) {
      const [key, ...rest] = part.split("=");
      if (key) pairs[key.trim()] = rest.join("=").trim();
    }
    setAdding(true);
    try {
      await sourcesApi.createSample(sourceName, { name, path, params: pairs });
      setName(""); setPath(""); setParams("");
      await onChanged();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setAdding(false);
    }
  };

  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-semibold text-ink">{T.samples}</h3>
        <p className="text-sm text-ink-soft">{T.samplesHelp}</p>
      </div>
      {samples.length ? (
        <ul className="space-y-2">
          {samples.map((sample) => (
            <SampleCard key={sample.id} sample={sample}
                        onRun={async () => {
                          try {
                            await sourcesApi.runSample(sourceName, sample.id);
                          } catch (err) {
                            onError(err instanceof ApiError ? err.message : t.common.unexpected);
                          }
                          await onChanged();
                        }}
                        onDelete={async () => {
                          try {
                            await sourcesApi.deleteSample(sourceName, sample.id);
                          } catch (err) {
                            onError(err instanceof ApiError ? err.message : t.common.unexpected);
                          }
                          await onChanged();
                        }} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-soft">{T.restEmpty}</p>
      )}
      <div className="space-y-3 rounded-card bg-surface-2 p-3">
        <Input label={T.sampleName} value={name} maxLength={80}
               onChange={(e) => setName(e.target.value)} />
        <Input label={T.samplePath} value={path} maxLength={500} placeholder="v1/listings"
               onChange={(e) => setPath(e.target.value)} />
        <Input label={T.sampleParams} value={params} placeholder="limit=100"
               onChange={(e) => setParams(e.target.value)} />
        <Button variant="secondary" icon={<Plus className="h-4 w-4" aria-hidden />}
                loading={adding} disabled={!name.trim() || !path.trim()} onClick={add}>
          {T.sampleAdd}
        </Button>
      </div>
    </section>
  );
}

export function SourceStructure({ source }: { source: DataSource }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const toast = useToast();
  const [pack, setPack] = useState<StructurePack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [samples, setSamples] = useState<SampleRequest[]>([]);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await sourcesApi.structure(source.name);
      setPack(next);
      setNotes(next.pack.notes);
      if (source.kind === "rest" || source.kind === "supabase") {
        setSamples(await sourcesApi.samples(source.name));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setLoading(false);
    }
  }, [source.name, source.kind, t]);

  useEffect(() => { void load(); }, [load]);

  const saveNotes = async () => {
    setSavingNotes(true);
    try {
      await sourcesApi.saveNotes(source.name, notes);
      toast(T.notesSaved);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      setSavingNotes(false);
    }
  };

  const structure = pack?.structure;

  return (
    <div className={SPLIT_ASIDE}>
      <div className="space-y-4">
        <Card className="space-y-3 p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-semibold text-ink">{T.title}</h2>
              <p className="text-sm text-ink-soft">{T.subtitle}</p>
            </div>
            <Button variant="ghost" size="sm" icon={<RefreshCw className="h-4 w-4" aria-hidden />}
                    loading={loading} onClick={() => void load()}>
              {loading ? T.refreshing : T.refresh}
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href={sourcesApi.downloadUrl(source.name, "md")}
              download={`structure-${source.name}.md`}
              className="inline-flex min-h-tap items-center rounded-btn border border-line bg-surface px-3 text-sm font-medium text-ink hover:border-line-accent"
            >
              <Download className="mr-1.5 h-4 w-4" aria-hidden />{T.downloadMd}
            </a>
            <a
              href={sourcesApi.downloadUrl(source.name, "json")}
              download={`structure-${source.name}.json`}
              className="inline-flex min-h-tap items-center rounded-btn border border-line bg-surface px-3 text-sm font-medium text-ink hover:border-line-accent"
            >
              <Download className="mr-1.5 h-4 w-4" aria-hidden />{T.downloadJson}
            </a>
            <Button variant="secondary" className="lg:hidden" onClick={() => setChatOpen(true)}>
              {t.sourceChat.title}
            </Button>
          </div>
          {pack?.pack.truncated ? <Alert tone="warning">{T.truncated}</Alert> : null}
          {error ? (
            <Alert tone="error"
                   action={<Button variant="secondary" onClick={() => void load()}>{t.common.retry}</Button>}>
              {error}
            </Alert>
          ) : null}
          {actionError ? <Alert tone="error">{actionError}</Alert> : null}
        </Card>

        <Card className="space-y-4 p-4 sm:p-5">
          {loading && !pack ? (
            <div role="status" className="flex justify-center py-8 text-accent">
              <Spinner className="h-7 w-7" />
              <span className="sr-only">{t.common.loading}</span>
            </div>
          ) : !structure ? null : structure.kind === "postgresql" ? (
            <>
              <Input label={T.search} value={query} placeholder={T.search}
                     onChange={(e) => setQuery(e.target.value)} />
              <PostgresStructure pack={pack!} sourceName={source.name} query={query}
                                 onChanged={() => void load()}
                                 onError={setActionError} />
            </>
          ) : structure.kind === "rest" || structure.kind === "supabase" ? (
            <RestSamples sourceName={source.name} samples={samples} onChanged={load}
                         onError={setActionError} />
          ) : structure.kind === "soap" ? (
            <section className="space-y-2">
              <h3 className="font-semibold text-ink">{T.operations}</h3>
              {(structure.services ?? []).length ? (
                <ul className="space-y-2">
                  {(structure.services ?? []).flatMap((service) =>
                    service.ports.flatMap((port) => port.operations.map((operation) => (
                      <li key={`${service.name}.${port.name}.${operation.name}`}
                          className="rounded-card border border-line p-3">
                        <p className="break-words font-medium text-ink">{operation.name}</p>
                        <p className="break-words text-sm text-ink-muted">
                          {operation.input ?? "—"} → {operation.output ?? "—"}
                        </p>
                      </li>
                    ))))}
                </ul>
              ) : (
                <EmptyState title={T.soapEmpty}>{T.soapEmpty}</EmptyState>
              )}
            </section>
          ) : null}
        </Card>

        <Card className="space-y-3 p-4 sm:p-5">
          <div>
            <h3 className="font-semibold text-ink">{T.notes}</h3>
            <p className="text-sm text-ink-soft">{T.notesHelp}</p>
          </div>
          <label className="block text-sm font-semibold text-ink-2" htmlFor="structure-notes">
            {T.notes}
          </label>
          <textarea
            id="structure-notes"
            value={notes}
            maxLength={4000}
            rows={4}
            placeholder={T.notesPlaceholder}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded-field border border-line-strong bg-surface px-3 py-2 text-ink"
          />
          <Button variant="secondary" loading={savingNotes} onClick={saveNotes}>
            {T.saveNotes}
          </Button>
        </Card>
      </div>

      <div className="hidden min-w-0 lg:block">
        <StructureChat sourceName={source.name} />
      </div>

      {chatOpen ? (
        <div className="fixed inset-x-0 bottom-0 z-30 max-h-[75dvh] overflow-y-auto rounded-t-2xl border-t border-line bg-surface p-3 shadow-lg lg:hidden">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center text-sm font-semibold text-ink-soft">
              <AlertTriangle className="mr-1.5 h-4 w-4" aria-hidden />{T.title}
            </span>
            <Button variant="ghost" size="sm" onClick={() => setChatOpen(false)}>
              {t.common.close}
            </Button>
          </div>
          <StructureChat sourceName={source.name} />
        </div>
      ) : null}
    </div>
  );
}
