import { gapPath } from "./chartScale";
import { strokeClass } from "../layoutRoles";
import type { ColorRole } from "../../../api/types";

/** A KPI's own series, drawn small enough to sit under a value. Decorative: the value, the label
 * and the change chip already carry the meaning. */
export function Sparkline({
  values,
  role = "series1",
  className = "",
}: {
  values: (number | null)[];
  role?: ColorRole;
  className?: string;
}) {
  const numbers = values.filter((value): value is number => value !== null);
  if (numbers.length < 2) return null;

  const width = 96;
  const height = 24;
  const lo = Math.min(...numbers);
  const hi = Math.max(...numbers);
  const span = hi - lo || 1;
  const x = (i: number) => (values.length === 1 ? width / 2 : (i / (values.length - 1)) * width);
  const y = (value: number) => height - 3 - ((value - lo) / span) * (height - 6);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden
      className={`h-5 w-full max-w-[8rem] ${className}`}
    >
      <path
        d={gapPath(values, x, y)}
        fill="none"
        className={strokeClass(role)}
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    </svg>
  );
}
