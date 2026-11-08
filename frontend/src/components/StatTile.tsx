import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Link } from "react-router";
import { Card } from "./Card";
import { numberFormat } from "../lib/intl";

export interface StatTileDelta {
  value: number;
  suffix?: string;
  label?: string;
  positiveIsGood?: boolean;
}

export interface StatTileProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  footnote?: ReactNode;
  delta?: StatTileDelta;
  className?: string;
  size?: "normal" | "tv";
  /** Feature 061: where the counter goes when it is pressed (the menu option it counts). */
  to?: string;
}

export function StatTile({
  label,
  value,
  icon,
  footnote,
  delta,
  className = "",
  size = "normal",
  to,
}: StatTileProps) {
  const formattedDelta = delta
    ? numberFormat({ signDisplay: "exceptZero", maximumFractionDigits: 1 }).format(delta.value) +
      (delta.suffix ?? "")
    : undefined;

  const good = delta && delta.value !== 0 ? delta.value > 0 === (delta.positiveIsGood ?? true) : null;
  const deltaColor = good === null ? "text-ink-muted" : good ? "text-success" : "text-danger";
  const DeltaIcon = delta ? (delta.value > 0 ? ArrowUpRight : delta.value < 0 ? ArrowDownRight : Minus) : null;

  const body = (
    <>
      <div className="flex items-center gap-3">
        {icon ? (
          <span
            aria-hidden
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent"
          >
            {icon}
          </span>
        ) : null}
        <span
          className={
            size === "tv"
              ? "text-sm font-medium text-ink-muted sm:text-base xl:text-xl"
              : "text-xs font-medium text-ink-muted"
          }
        >
          {label}
        </span>
      </div>
      <div className="mt-3 text-2xl font-bold tracking-tight text-ink break-words">{value}</div>
      {footnote ? <div className="mt-1 text-xs text-ink-muted">{footnote}</div> : null}
      {delta && formattedDelta ? (
        <div className={`mt-2 inline-flex items-center gap-1 text-xs font-semibold ${deltaColor}`}>
          {DeltaIcon ? <DeltaIcon className="h-3.5 w-3.5" aria-hidden /> : null}
          {formattedDelta}
          {delta.label ? <span className="font-normal text-ink-muted">{` ${delta.label}`}</span> : null}
        </div>
      ) : null}
    </>
  );

  if (!to) return <Card className={`p-5 ${className}`}>{body}</Card>;
  return (
    <Link
      to={to}
      data-testid="stat-tile-link"
      className={`card-surface block rounded-card border border-line bg-surface p-5 transition-colors transition-shadow hover:border-line-accent hover:shadow-raised ${className}`}
    >
      {body}
    </Link>
  );
}
