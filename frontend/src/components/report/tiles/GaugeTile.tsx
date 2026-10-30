import type { KpiItem, WebComponent } from "../../../api/types";
import { localized } from "../../../lib/labels";
import { formatValue } from "../../../lib/numbers";

const BAND_COLORS = [
  "var(--negative)",
  "var(--series-5)",
  "var(--neutral)",
  "var(--series-3)",
  "var(--positive)",
];

const CX = 100;
const CY = 100;
const R = 80;

function polar(angleDeg: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: CX + R * Math.cos(rad), y: CY - R * Math.sin(rad) };
}

function arcPath(fromDeg: number, toDeg: number): string {
  const start = polar(fromDeg);
  const end = polar(toDeg);
  // semicircle radius 80, sweep clockwise (1) going from 180° to 0°.
  return `M ${start.x} ${start.y} A ${R} ${R} 0 0 1 ${end.x} ${end.y}`;
}

export function GaugeTile({ component, items }: { component: WebComponent; items: KpiItem[] }) {
  const item = component.metric ? items.find((i) => i.metric === component.metric) : undefined;
  const label = item ? localized(item, "label") : localized(component, "title");
  const raw = item?.value;
  const value = Number(raw);
  const min = component.min ?? 0;
  const max = component.max ?? 100;
  const hasValue = raw !== null && raw !== undefined && Number.isFinite(value);
  const ratio = hasValue && max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0;
  const angle = 180 - ratio * 180;
  const needle = polar(angle);
  const shown = hasValue ? formatValue(raw, item?.format ?? "number") : "—";

  return (
    <div className="h-full rounded-card border border-line bg-surface p-4 shadow-card">
      <svg viewBox="0 0 200 110" role="img" aria-label={`${label}: ${shown}`} className="mx-auto block w-full max-w-[280px]">
        {BAND_COLORS.map((color, i) => {
          const from = 180 - (i * 180) / 5;
          const to = 180 - ((i + 1) * 180) / 5;
          return (
            <path
              key={i}
              d={arcPath(from, to)}
              style={{ stroke: color }}
              strokeWidth={14}
              fill="none"
              strokeLinecap="butt"
            />
          );
        })}
        <line
          x1={CX}
          y1={CY}
          x2={needle.x}
          y2={needle.y}
          style={{ stroke: "var(--kpi-text-color)" }}
          strokeWidth={3}
          strokeLinecap="round"
        />
        <circle cx={CX} cy={CY} r={5} style={{ fill: "var(--kpi-text-color)" }} />
        <text
          x={CX}
          y={92}
          textAnchor="middle"
          fontSize={28}
          fontWeight={700}
          fill="currentColor"
        >
          {shown}
        </text>
      </svg>
      <div className="mt-2 text-center text-sm text-ink-muted">{label}</div>
    </div>
  );
}
