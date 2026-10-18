import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  actions?: ReactNode;
  badge?: ReactNode;
}

export function PageHeader({ title, subtitle, action, actions, badge }: PageHeaderProps) {
  const hasActions = action !== undefined || actions !== undefined;
  return (
    <div className="mb-6 rounded-card border border-line-accent bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-ink break-words sm:text-3xl">{title}</h1>
            {badge ? badge : null}
          </div>
          {subtitle ? <p className="mt-1 text-sm text-ink-muted sm:text-base">{subtitle}</p> : null}
        </div>
        {hasActions ? (
          <div className="flex flex-wrap items-center gap-2">
            {action}
            {actions}
          </div>
        ) : null}
      </div>
    </div>
  );
}
