import { RefreshCw, WifiOff } from "lucide-react";
import { useId } from "react";
import { useT } from "../../i18n";
import {
  AUTO_REFRESH_MODES,
  formatClock,
  type AutoRefreshMode,
  type AutoRefreshStatus,
} from "../../lib/autoRefresh";
import { Select } from "../Select";

export function AutoRefreshControl({
  mode,
  onChange,
  cacheSeconds,
  compact = false,
}: {
  mode: AutoRefreshMode;
  onChange: (m: AutoRefreshMode) => void;
  cacheSeconds?: number | null;
  /** Feature 030: no heading, no border — a single field inside the parameter panel's row. */
  compact?: boolean;
}) {
  const t = useT();
  const headingId = useId();
  const dataLabel = cacheSeconds && cacheSeconds > 0
    ? `${t.autoRefresh.modes.data} (${t.autoRefresh.directEvery(Math.max(1, Math.round(cacheSeconds / 60)))})`
    : t.autoRefresh.modes.data;

  if (compact) {
    return (
      <div className="min-w-[9rem] flex-1">
        <Select
          label={t.autoRefresh.frequency}
          value={mode}
          onChange={(e) => onChange(e.target.value as AutoRefreshMode)}
        >
          {AUTO_REFRESH_MODES.map((m) => (
            <option key={m} value={m}>
              {m === "data" ? dataLabel : t.autoRefresh.modes[m]}
            </option>
          ))}
        </Select>
      </div>
    );
  }

  return (
    <section aria-labelledby={headingId} className="mt-5 space-y-4 border-t border-line pt-5">
      <h3 id={headingId} className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
        {t.autoRefresh.label}
      </h3>

      <Select
        label={t.autoRefresh.frequency}
        value={mode}
        onChange={(e) => onChange(e.target.value as AutoRefreshMode)}
        hint={t.autoRefresh.hint}
      >
        {AUTO_REFRESH_MODES.map((m) => (
          <option key={m} value={m}>
            {m === "data" ? dataLabel : t.autoRefresh.modes[m]}
          </option>
        ))}
      </Select>
    </section>
  );
}

export function AutoRefreshStatusLine({
  status,
  lastAt,
  className,
}: {
  status: AutoRefreshStatus | "off";
  lastAt: Date | null;
  className?: string;
}) {
  const t = useT();
  if (status === "off") return null;

  if (status === "offline") {
    return (
      <p
        role="status"
        data-testid="autorefresh-status"
        className={`flex items-center gap-2 text-sm text-warning-strong ${className ?? ""}`}
      >
        <WifiOff className="h-4 w-4 shrink-0" aria-hidden />
        {t.autoRefresh.offline}
      </p>
    );
  }

  return (
    <p
      role="status"
      data-testid="autorefresh-status"
      className={`flex items-center gap-2 text-sm text-ink-muted ${className ?? ""}`}
    >
      <RefreshCw className="h-4 w-4 shrink-0" aria-hidden />
      {t.autoRefresh.status(lastAt ? formatClock(lastAt) : "—")}
    </p>
  );
}
