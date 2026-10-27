import type { RenderErrorCard as Card } from "../../api/types";
import { useT } from "../../i18n";

/**
 * Feature 038 FR-006: one tile (or one PDF block) that cannot render says which piece failed and
 * how to look it up. The rest of the dashboard keeps rendering; nothing here ever shows a row
 * value, only codes and identifiers.
 */
export function RenderErrorCard({ error }: { error: Card }) {
  const t = useT();
  const details = t.report.errors;
  const rows: [string, string | undefined][] = [
    [details.code, error.code],
    [details.report, error.report],
    [details.reference, error.reference],
    [details.dataset, error.dataset ?? error.datasets],
    [details.column, error.column],
    [details.sets, error.sets],
    [details.key, error.key],
    [details.metric, error.metric],
    [details.view, error.view],
    [details.component, error.component],
    [details.type, error.type],
    [details.block, error.block],
    [details.reason, error.reason],
    [details.format, error.format],
    [details.version, error.version === undefined ? undefined : String(error.version)],
  ];
  const shown = rows.filter(([, value]) => value !== undefined && value !== "");

  return (
    <div role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger-deep ring-1 ring-inset ring-danger-line">
      <p className="font-semibold [overflow-wrap:anywhere]">{error.message}</p>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide">{details.title}</summary>
        <dl className="mt-1 grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5 text-xs">
          {shown.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="font-semibold">{label}</dt>
              <dd className="font-mono [overflow-wrap:anywhere]">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-1 text-xs">{details.log}</p>
        <code className="mt-0.5 block break-all rounded bg-surface-2 p-1 font-mono text-[11px]">{details.cmd(error.reference)}</code>
      </details>
    </div>
  );
}

/** Feature 038: an empty period is a state, not a failure: the tile says «Sin datos». */
export function NoDataCard({ error }: { error?: Card }) {
  const t = useT();
  return (
    <div role="status" className="rounded-xl bg-surface-2 p-3 text-sm text-ink-muted ring-1 ring-inset ring-line">
      <p>{error?.message || t.report.errors.noData}</p>
      {error ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide">
            {t.report.errors.title}
          </summary>
          <p className="mt-1 font-mono text-[11px] [overflow-wrap:anywhere]">
            {[error.code, error.datasets ?? error.dataset, error.reference]
              .filter((value) => value !== undefined && value !== "")
              .join(" · ")}
          </p>
        </details>
      ) : null}
    </div>
  );
}
