import type { ReportImageSet, WebComponent } from "../../../api/types";
import { formatValue, formatValueCompact } from "../../../lib/numbers";
import { ReportImage } from "../ReportImage";

type AssetView = { rows: Record<string, unknown>[] };

type Roles = {
  image: string | null;
  title: string | null;
  subtitle: string | null;
  value: string | null;
  delta: string | null;
};

function resolveRoles(component: WebComponent): Roles {
  const cols = Array.isArray(component.columns) ? component.columns : [];
  const pick = (i: number): string | null => {
    const c = cols[i];
    return typeof c === "string" && c !== "" ? c : null;
  };
  return {
    image: pick(0),
    title: pick(1),
    subtitle: pick(2),
    value: pick(3),
    delta: pick(4),
  };
}

function asString(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

export function AssetGrid({
  component,
  view,
  image,
}: {
  component: WebComponent;
  view: AssetView;
  /** Feature 044: a declared image set; its key column takes the place of the first role. */
  image?: ReportImageSet;
}) {
  const roles = resolveRoles(component);
  const rows = Array.isArray(view.rows) ? view.rows : [];
  const limit = component.limit ?? 8;
  const visible = rows.slice(0, limit);

  if (visible.length === 0) {
    return (
      <div className="h-full rounded-card border border-line bg-surface p-4 shadow-card text-ink-muted">
        —
      </div>
    );
  }

  return (
    <div className="h-full rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {visible.map((row, idx) => {
          const imageSrc = !image && roles.image ? asString(row[roles.image]) : "";
          const imageName = image ? row[image.key] : undefined;
          const title = roles.title ? asString(row[roles.title]) : "";
          const subtitle = roles.subtitle ? asString(row[roles.subtitle]) : "";
          const rawValue = roles.value ? row[roles.value] : undefined;
          const numValue = Number(rawValue);
          const shownValue =
            rawValue !== null &&
            rawValue !== undefined &&
            rawValue !== "" &&
            Number.isFinite(numValue)
              ? formatValueCompact(numValue, "number")
              : asString(rawValue) || "—";
          const rawDelta = roles.delta ? row[roles.delta] : undefined;
          const pct =
            rawDelta !== null &&
            rawDelta !== undefined &&
            rawDelta !== "" &&
            Number.isFinite(Number(rawDelta))
              ? Number(rawDelta)
              : null;
          const positive = pct !== null && pct >= 0;

          return (
            <div key={idx} className="flex min-w-0 flex-col gap-1">
              {image ? <ReportImage set={image} name={imageName} size={40} /> : null}
              {roles.image && imageSrc ? (
                <span>
                  <img
                    className="h-10 w-10 rounded-full"
                    src={imageSrc}
                    alt={title}
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                </span>
              ) : null}
              {title ? <div className="text-lg font-bold">{title}</div> : null}
              {subtitle ? <div className="truncate text-xs text-ink-muted">{subtitle}</div> : null}
              <div className="text-2xl font-bold tabular-nums whitespace-nowrap">{shownValue}</div>
              {pct !== null ? (
                <span
                  className="inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold"
                  style={{
                    backgroundColor: positive
                      ? "var(--kpi-delta-bg-pos)"
                      : "var(--kpi-delta-bg-neg)",
                    color: positive
                      ? "var(--positive)"
                      : "var(--negative)",
                  }}
                >
                  {positive ? "▲" : "▼"} {formatValue(pct, "percent")}
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
