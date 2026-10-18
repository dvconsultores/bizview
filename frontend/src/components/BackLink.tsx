import { ArrowLeft } from "lucide-react";
import type { MouseEvent } from "react";
import { Link } from "react-router";
import { useT } from "../i18n";

export interface BackLinkProps {
  to: string;
  className?: string;
  /** Runs before navigating; `event.preventDefault()` stays on the page (unsaved-changes guard). */
  onNavigate?: (event: MouseEvent<HTMLAnchorElement>) => void;
}

/** The one back control of the app: an arrow and "Volver" (never the destination's name). */
export function BackLink({ to, className = "mb-4", onNavigate }: BackLinkProps) {
  const t = useT();
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className={`control-compact inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 text-sm font-medium text-ink-2 transition-colors hover:bg-subtle hover:text-ink ${className}`}
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      {t.common.back}
    </Link>
  );
}
