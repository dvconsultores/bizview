import { AlertTriangle, CheckCircle2, Power } from "lucide-react";
import { Link } from "react-router";
import type { AIHealth } from "../../api/types";
import { aiHealthState } from "../../api/ai";
import { useT } from "../../i18n";

/**
 * The AI state as one small pill (feature 035): off, working, or failing with its code.
 *
 * Shown in the composer while the provider is unhealthy — so the next dead turn is not a surprise —
 * and on the administration home.
 */
export function AIPill({ health, compact = true }: { health: AIHealth | null; compact?: boolean }) {
  const t = useT();
  const state = aiHealthState(health);
  if (state === "unknown" || state === "ok") {
    if (!compact && state === "ok") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success-deep">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          {t.ai.pillOk}
        </span>
      );
    }
    return null;
  }
  if (state === "off") {
    return (
      <Link to="/admin/ia"
            className="inline-flex items-center gap-1 rounded-full bg-subtle px-2 py-0.5 text-xs font-medium text-ink-muted hover:text-ink">
        <Power className="h-3.5 w-3.5" aria-hidden />
        {t.ai.pillOff}
      </Link>
    );
  }
  const code = health?.last_error_code ?? "provider_error";
  return (
    <Link to="/admin/ia"
          title={t.ai.errorCodes[code] ?? t.ai.errorCodes.provider_error}
          className="inline-flex min-h-tap items-center gap-1 rounded-full bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger hover:bg-danger-soft/70">
      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
      <span className="font-mono">{code}</span>
      <span className="sr-only">{t.ai.pillError}</span>
    </Link>
  );
}
