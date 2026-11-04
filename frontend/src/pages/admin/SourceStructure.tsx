import {
  AlertTriangle, ChevronRight, Download, Plus, RefreshCw, Sparkles, Trash2, X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { sourcesApi } from "../../api/sources";
import type {
  DataSource, GeneratedPack, GeneratedTable, SampleRequest, StructureState,
} from "../../api/types";
import { Alert } from "../../components/Alert";
import { Badge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Input } from "../../components/Input";
import { Spinner } from "../../components/Spinner";
import { useToast } from "../../components/Toast";
import { useT } from "../../i18n";
import { PAGE_STACK } from "../../lib/layout";

/**
 * Feature 052: the Estructura tab (converged 2026-11-03).
 *
 * One button generates the pack the external AI reads: Bizview scans the source, an internal AI
 * pass identifies tables, fields, relations and notes, product code verifies every name, and the
 * result is saved. The plain scan is what shows and downloads when no run exists or a run fails.
 * Nothing on this page reads a row value.
 */
function diffPacks(before: GeneratedPack | null, after: GeneratedPack | null) {
  const fields = (pack: GeneratedPack | null) => {
    const out = new Map<string, Set<string>>();
    for (const table of pack?.tables ?? []) {
      out.set(table.id, new Set(table.fields.map((f) => f.name)));
    }
    return out;
  };
  const a = fields(before);
  const b = fields(after);
  const addedTables = [...b.keys()].filter((id) => !a.has(id));
  const removedTables = [...a.keys()].filter((id) => !b.has(id));
  const changed = [...b.keys()]
    .filter((id) => a.has(id))
    .map((id) => ({
      id,
      fields: [...(b.get(id) ?? [])].filter((f) => !(a.get(id) ?? new Set<string>()).has(f)),
    }))
    .filter((entry) => entry.fields.length > 0);
  return { addedTables, removedTables, changed };
}

function FieldTable({ table }: { table: GeneratedTable }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-ink-soft">
          <tr>
            <th className="py-1 pr-3 font-semibold">{T.column}</th>
            <th className="py-1 pr-3 font-semibold">{T.type}</th>
            <th className="py-1 pr-3 font-semibold">{T.semantic}</th>
            <th className="py-1 font-semibold">{T.personal}</th>
          </tr>
        </thead>
        <tbody>
          {table.fields.map((field) => (
            <tr key={field.name} className="border-t border-line align-top">
              <td className="break-words py-2 pr-3 font-medium text-ink">
                {field.name}
                {field.path ? (
                  <span className="block text-xs font-normal text-ink-muted">{field.path}</span>
                ) : null}
              </td>
              <td className="break-words py-2 pr-3 text-ink-muted">
                {field.type}
                {field.unit ? ` · ${field.unit}` : ""}
                {field.units ? ` · ${field.units}` : ""}
              </td>
              <td className="py-2 pr-3 text-ink-muted">
                {field.semantic && field.semantic !== "text" && field.semantic !== "unknown" ? (
                  <Badge tone="gray">{field.semantic}</Badge>
                ) : null}
              </td>
              <td className="py-2">
                {field.personal ? <Badge tone="amber">{T.personalChip}</Badge> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GeneratedView({ pack, query }: { pack: GeneratedPack; query: string }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const relations = pack.relations ?? [];
  const metrics = pack.suggested_metrics ?? [];
  const needle = query.trim().toLowerCase();
  const tables = needle
    ? pack.tables.filter((table) =>
        [table.id, table.schema, table.row_is, ...table.fields.map((f) => f.name)]
          .some((value) => (value ?? "").toLowerCase().includes(needle)))
    : pack.tables;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge tone="green" icon={<Sparkles className="h-3.5 w-3.5" aria-hidden />}>
          {T.generatedBadge}
        </Badge>
        <span className="text-ink-muted">
          {T.generatedAt(new Date(pack.generated_at).toLocaleString())}
          {pack.generator.model ? ` · ${pack.generator.model}` : ""}
          {pack.generator.tokens ? ` · ${T.tokens(pack.generator.tokens)}` : ""}
        </span>
      </div>
      {pack.generator.incomplete?.length ? (
        <Alert tone="warning">{T.incomplete(pack.generator.incomplete.join(", "))}</Alert>
      ) : null}
      {needle && !tables.length ? (
        <p className="text-sm text-ink-soft">{T.searchEmpty(query)}</p>
      ) : null}
      <ul className="space-y-2">
        {tables.map((table) => (
          <li key={table.id}>
            <details className="rounded-card border border-line bg-surface">
              <summary className="flex min-h-tap cursor-pointer items-center px-3 py-2">
                <ChevronRight className="mr-1.5 h-4 w-4 shrink-0 text-ink-soft" aria-hidden />
                <span className="min-w-0 flex-1 break-words font-medium text-ink">{table.id}</span>
                <span className="ml-2 flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                  {table.path ? (
                    <code className="text-xs text-ink-muted">{table.path}</code>
                  ) : null}
                  <span className="text-xs text-ink-muted">{T.columns(table.fields.length)}</span>
                  {table.row_count != null ? (
                    <span className="text-xs text-ink-muted">{T.rows(table.row_count)}</span>
                  ) : null}
                </span>
              </summary>
              <div className="space-y-3 px-3 pb-3">
                {table.row_is ? <p className="text-sm text-ink-2">{table.row_is}</p> : null}
                <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                  {table.key?.length ? (
                    <div><dt className="inline font-semibold">{T.key}: </dt>
                      <dd className="inline"><code>{table.key.join(", ")}</code></dd></div>
                  ) : null}
                  {table.date_field ? (
                    <div><dt className="inline font-semibold">{T.dateField}: </dt>
                      <dd className="inline"><code>{table.date_field}</code></dd></div>
                  ) : null}
                  {table.records ? (
                    <div><dt className="inline font-semibold">{T.sampleRecords}: </dt>
                      <dd className="inline"><code>{table.records}</code></dd></div>
                  ) : null}
                  {table.pagination?.type ? (
                    <div><dt className="inline font-semibold">{T.samplePagination}: </dt>
                      <dd className="inline">{table.pagination.type}</dd></div>
                  ) : null}
                </dl>
                <FieldTable table={table} />
                {table.notes?.length ? (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-ink-soft">
                    {table.notes.map((note) => <li key={note}>{note}</li>)}
                  </ul>
                ) : null}
              </div>
            </details>
          </li>
        ))}
      </ul>
      {relations.length ? (
        <section className="space-y-2">
          <h3 className="font-semibold text-ink">{T.relations}</h3>
          <ul className="space-y-1 text-sm text-ink-2">
            {relations.map((relation) => (
              <li key={`${relation.from}-${relation.to}`} className="break-words">
                <code>{relation.from}</code> → <code>{relation.to}</code>{" "}
                <span className="text-ink-muted">{relation.kind}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {metrics.length ? (
        <section className="space-y-2">
          <h3 className="font-semibold text-ink">{T.metrics}</h3>
          <p className="text-sm text-ink-soft">{T.metricsHelp}</p>
          <ul className="space-y-1 text-sm text-ink-2">
            {metrics.map((metric) => (
              <li key={metric.id} className="break-words">
                <code>{metric.id}</code> — {metric.formula_words}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {pack.dropped?.length ? (
        <section className="space-y-2">
          <h3 className="flex items-center font-semibold text-ink">
            <AlertTriangle className="mr-1.5 h-4 w-4 text-warning" aria-hidden />{T.dropped}
          </h3>
          <p className="text-sm text-ink-soft">{T.droppedHelp}</p>
          <ul className="flex flex-wrap gap-1.5">
            {pack.dropped.map((item) => (
              <li key={item}
                  className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">
                {item}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function ScanView({ state, query, onChanged, onError }:
  { state: StructureState; query: string; onChanged: () => void;
    onError: (m: string) => void }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const scan = state.scan;
  if (!scan) return null;
  const all = scan.structure.tables ?? [];
  const needle = query.trim().toLowerCase();
  const tables = needle
    ? all.filter((table) =>
        [table.name, table.schema, ...table.columns.map((c) => c.name)]
          .some((value) => (value ?? "").toLowerCase().includes(needle)))
    : all;
  if (!tables.length) return <p className="text-sm text-ink-soft">{T.searchEmpty(query)}</p>;
  const bySchema = new Map<string, typeof tables>();
  for (const table of tables) {
    const schema = table.schema ?? "public";
    if (!bySchema.has(schema)) bySchema.set(schema, []);
    bySchema.get(schema)!.push(table);
  }
  return (
    <div className="space-y-5">
      {[...bySchema.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([schema, items]) => (
        <section key={schema} className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">
            {T.schema} <span className="text-ink">{schema}</span>
          </h3>
          <ul className="space-y-2">
            {items.map((table) => (
              <li key={`${schema}.${table.name}`}>
                <details className="rounded-card border border-line bg-surface">
                  <summary className="flex min-h-tap cursor-pointer items-center px-3 py-2">
                    <ChevronRight className="mr-1.5 h-4 w-4 shrink-0 text-ink-soft" aria-hidden />
                    <span className="min-w-0 flex-1 break-words font-medium text-ink">
                      {table.name}
                    </span>
                    <span className="ml-2 flex shrink-0 items-center gap-1.5">
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
                          <tr key={column.name} className="border-t border-line">
                            <td className="break-words py-2 pr-3 font-medium text-ink">
                              {column.name}
                            </td>
                            <td className="break-words py-2 pr-3 text-ink-muted">{column.type}</td>
                            <td className="py-2 pr-3 text-ink-muted">
                              {column.nullable ? T.nullable : "—"}
                            </td>
                            <td className="py-2 pr-3 text-ink-muted">
                              {column.range
                                ? T.dates(column.range.min ?? "…", column.range.max ?? "…")
                                : "—"}
                            </td>
                            <td className="py-2">
                              <button
                                type="button"
                                aria-pressed={!!column.personal}
                                title={T.personalHelp}
                                onClick={async () => {
                                  try {
                                    await sourcesApi.setPersonal(scan.pack.source, {
                                      schema_name: schema, table: table.name,
                                      column: column.name, personal: !column.personal,
                                    });
                                    onChanged();
                                  } catch (err) {
                                    onError(err instanceof ApiError ? err.message
                                                                    : t.common.unexpected);
                                  }
                                }}
                                className={`inline-flex min-h-tap items-center rounded-full px-2 py-1 text-xs font-semibold ${
                                  column.personal
                                    ? "bg-warning-soft text-warning"
                                    : "text-ink-soft hover:bg-surface-2"}`}>
                                {column.personal ? T.personalChip : T.personal}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function SampleCard({ sample, onRun, onDelete, onError }:
  { sample: SampleRequest; onRun: () => Promise<void>; onDelete: () => Promise<void>;
    onError: (m: string) => void }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const [busy, setBusy] = useState(false);
  const suggestions = (sample.last_suggestions ?? {}) as Record<string, unknown>;
  const fields = (suggestions.fields ?? {}) as Record<string, string>;
  return (
    <li className="rounded-card border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 break-words font-medium text-ink">{sample.name}</span>
        <Badge tone="blue">{sample.method}</Badge>
        <Button variant="ghost" size="sm" aria-label={`${T.sampleDelete}: ${sample.name}`}
                onClick={() => void onDelete()}>
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
          {suggestions.timestamp_units ? (
            <div><dt className="inline font-semibold">{T.sampleUnits}: </dt>
              <dd className="inline">{String(suggestions.timestamp_units)}</dd></div>
          ) : null}
          {suggestions.pagination ? (
            <div><dt className="inline font-semibold">{T.samplePagination}: </dt>
              <dd className="inline">{String(suggestions.pagination)}</dd></div>
          ) : null}
        </dl>
      ) : (
        <p className="mt-2 text-xs text-ink-muted">{T.sampleNone}</p>
      )}
      <Button variant="secondary" size="sm" className="mt-2" loading={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await onRun();
                } catch (err) {
                  onError(err instanceof ApiError ? err.message : t.common.unexpected);
                } finally {
                  setBusy(false);
                }
              }}>
        {busy ? T.sampleRunning : T.sampleRun}
      </Button>
    </li>
  );
}

function RestSamples({ sourceName, samples, onChanged, onError }:
  { sourceName: string; samples: SampleRequest[]; onChanged: () => Promise<void>;
    onError: (m: string) => void }) {
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
      setName("");
      setPath("");
      setParams("");
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
                          await sourcesApi.runSample(sourceName, sample.id);
                          await onChanged();
                        }}
                        onDelete={async () => {
                          await sourcesApi.deleteSample(sourceName, sample.id);
                          await onChanged();
                        }}
                        onError={onError} />
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

const STAGES = ["scan", "ai", "verify"] as const;

export function SourceStructure({ source }: { source: DataSource }) {
  const t = useT();
  const T = t.admin.sourceStructure;
  const toast = useToast();
  const [state, setState] = useState<StructureState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<"scan" | "ai" | "verify" | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [diff, setDiff] = useState<ReturnType<typeof diffPacks> | null>(null);
  const [samples, setSamples] = useState<SampleRequest[]>([]);
  const [notes, setNotes] = useState("");
  const [query, setQuery] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await sourcesApi.structureState(source.name);
      setState(next);
      setNotes(next.generated?.notes ?? next.scan?.pack.notes ?? "");
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

  const generate = async () => {
    setGenerationError(null);
    setDiff(null);
    setGenerating("scan");
    const controller = new AbortController();
    abort.current = controller;
    // One request runs the whole pipeline; these stages are what the server does, shown as progress.
    let step = 0;
    const tick = window.setInterval(() => {
      step = Math.min(step + 1, STAGES.length - 1);
      setGenerating(STAGES[step]);
    }, 2_500);
    try {
      const result = await sourcesApi.generate(source.name, controller.signal);
      setDiff(diffPacks(result.previous, result.pack));
      await load();
      toast(T.generatedOk);
    } catch (err) {
      setGenerationError(controller.signal.aborted ? T.cancelled
        : err instanceof ApiError ? err.message : t.common.unexpected);
    } finally {
      window.clearInterval(tick);
      setGenerating(null);
      abort.current = null;
    }
  };

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

  const generated = state?.generated ?? null;
  const progress = useMemo(
    () => ({ scan: T.stageScan, ai: T.stageAi, verify: T.stageVerify }), [T]);

  return (
    <div className={PAGE_STACK}>
      <Card className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-ink">{T.title}</h2>
            <p className="text-sm text-ink-soft">{T.subtitle}</p>
          </div>
          <Button variant="ghost" size="sm" icon={<RefreshCw className="h-4 w-4" aria-hidden />}
                  loading={loading && !generating}
                  onClick={() => void load()}>
            {loading && !generating ? T.refreshing : T.refresh}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon={<Sparkles className="h-4 w-4" aria-hidden />} loading={!!generating}
                  disabled={!state?.ai.enabled || source.kind === "soap"}
                  onClick={() => void generate()}>
            {generating ? T.generating : T.generate}
          </Button>
          <a href={sourcesApi.downloadUrl(source.name, "md")}
             download={`structure-${source.name}.md`}
             className="inline-flex min-h-tap items-center rounded-btn border border-line bg-surface px-3 text-sm font-medium text-ink hover:border-line-accent">
            <Download className="mr-1.5 h-4 w-4" aria-hidden />{T.downloadMd}
          </a>
          <a href={sourcesApi.downloadUrl(source.name, "json")}
             download={`structure-${source.name}.json`}
             className="inline-flex min-h-tap items-center rounded-btn border border-line bg-surface px-3 text-sm font-medium text-ink hover:border-line-accent">
            <Download className="mr-1.5 h-4 w-4" aria-hidden />{T.downloadJson}
          </a>
          {generated ? (
            <a href={sourcesApi.downloadUrl(source.name, "md", "scan")}
               className="inline-flex min-h-tap items-center px-3 text-sm font-medium text-ink-muted underline hover:text-ink">
              {T.downloadScan}
            </a>
          ) : null}
        </div>
        {state && !state.ai.enabled ? (
          <Alert tone="info"
                 action={<a className="font-semibold text-accent underline" href="/admin/ia">
                   {T.enableAi}
                 </a>}>
            {T.generateOff}
          </Alert>
        ) : null}
        {source.kind === "soap" ? <Alert tone="info">{T.generateSoap}</Alert> : null}
        {generating ? (
          <div className="space-y-2" aria-live="polite">
            <p className="text-sm text-ink-2">{progress[generating]}</p>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-accent transition-all"
                   style={{ width: `${(STAGES.indexOf(generating) + 1) * 33}%` }} />
            </div>
            <Button variant="ghost" size="sm" icon={<X className="h-4 w-4" aria-hidden />}
                    onClick={() => abort.current?.abort()}>
              {T.cancel}
            </Button>
          </div>
        ) : null}
        {generationError ? <Alert tone="error">{generationError}</Alert> : null}
        {diff ? (
          <div className="space-y-1 rounded-card bg-surface-2 p-3 text-sm" data-diff>
            <p className="font-semibold text-ink">{T.diffTitle}</p>
            {diff.addedTables.length ? (
              <p className="text-ink-2">{T.diffAdded(diff.addedTables.join(", "))}</p>
            ) : null}
            {diff.removedTables.length ? (
              <p className="text-ink-2">{T.diffRemoved(diff.removedTables.join(", "))}</p>
            ) : null}
            {diff.changed.map((entry) => (
              <p key={entry.id} className="text-ink-2">
                {T.diffChanged(entry.id, entry.fields.join(", "))}
              </p>
            ))}
            {!diff.addedTables.length && !diff.removedTables.length && !diff.changed.length ? (
              <p className="text-ink-muted">{T.diffSame}</p>
            ) : null}
          </div>
        ) : null}
        {error ? (
          <Alert tone="error"
                 action={<Button variant="secondary" onClick={() => void load()}>
                   {t.common.retry}
                 </Button>}>
            {error}
          </Alert>
        ) : null}
        {actionError ? <Alert tone="error">{actionError}</Alert> : null}
      </Card>

      <Card className="space-y-4 p-4 sm:p-5">
        {state && (generated || state.scan?.structure.kind !== "soap") ? (
          <Input label={T.search} value={query} placeholder={T.search}
                 onChange={(e) => setQuery(e.target.value)} />
        ) : null}
        {loading && !state ? (
          <div role="status" className="flex justify-center py-8 text-accent">
            <Spinner className="h-7 w-7" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        ) : null}
        {generated ? (
          <GeneratedView pack={generated} query={query} />
        ) : state?.scan?.structure.kind === "soap" ? (
          <section className="space-y-2">
            <h3 className="font-semibold text-ink">{T.operations}</h3>
            {(state.scan.structure.services ?? []).length ? (
              <ul className="space-y-2">
                {(state.scan.structure.services ?? []).flatMap((service) =>
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
        ) : state?.scan?.structure.kind === "postgresql" ? (
          <>
            <Alert tone="info">{T.scanOnly}</Alert>
            <ScanView state={state} query={query} onChanged={() => void load()}
                      onError={setActionError} />
          </>
        ) : state?.scan ? (
          /* A REST/Supabase scan has no catalogue to list: its content is the sample requests
             below, and this line is what says a generated pack does not exist yet. */
          <Alert tone="info">{T.scanOnly}</Alert>
        ) : null}
        {state?.scan_error ? <Alert tone="warning">{T.scanError(state.scan_error)}</Alert> : null}
      </Card>

      {source.kind === "rest" || source.kind === "supabase" ? (
        <Card className="space-y-4 p-4 sm:p-5">
          <RestSamples sourceName={source.name} samples={samples} onChanged={load}
                       onError={setActionError} />
        </Card>
      ) : null}

      <Card className="space-y-3 p-4 sm:p-5">
        <div>
          <h3 className="font-semibold text-ink">{T.notes}</h3>
          <p className="text-sm text-ink-soft">{T.notesHelp}</p>
        </div>
        <label className="block text-sm font-semibold text-ink-2" htmlFor="structure-notes">
          {T.notes}
        </label>
        <textarea id="structure-notes" value={notes} maxLength={4000} rows={4}
                  placeholder={T.notesPlaceholder}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full rounded-field border border-line-strong bg-surface px-3 py-2 text-ink" />
        <Button variant="secondary" loading={savingNotes} onClick={saveNotes}>
          {T.saveNotes}
        </Button>
      </Card>
    </div>
  );
}
