import { useId, type ReactNode } from "react";
import { Link } from "react-router";

export interface HubCardProps {
  to: string;
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  badge?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function HubCard({
  to,
  title,
  description,
  icon,
  badge,
  footer,
  className = "",
}: HubCardProps) {
  const titleId = useId();
  const descriptionId = useId();
  return (
    <Link
      to={to}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      className={`group flex h-full min-h-tap flex-col rounded-card border border-line bg-surface p-6 transition-colors transition-shadow hover:border-line-accent hover:shadow-raised ${className}`}
    >
      {(icon || badge) ? (
        <div className="flex items-start justify-between gap-3">
          {icon ? (
            <span
              aria-hidden
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent"
            >
              {icon}
            </span>
          ) : null}
          {badge}
        </div>
      ) : null}

      <span className={`min-w-0 ${icon || badge ? "mt-4" : ""}`}>
        <span id={titleId} className="font-semibold text-ink group-hover:text-accent">
          {title}
        </span>
        {description ? (
          <span id={descriptionId} className="mt-1 block text-sm text-ink-muted line-clamp-2">
            {description}
          </span>
        ) : null}
      </span>

      {footer ? <span className="mt-auto pt-4">{footer}</span> : null}
    </Link>
  );
}
