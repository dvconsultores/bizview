import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  actions?: ReactNode;
  badge?: ReactNode;
}

/**
 * One page header for every screen (feature 050, contract §3).
 *
 * It used to be a bordered card with a 2xl/3xl title, which on a phone took a fifth of the viewport
 * before any content and read as a hero block. It is now the page's title line: a compact heading, an
 * optional one-line subtitle, and the actions in one wrapping row — beside the title from `sm` up,
 * below it on a phone, so a long Spanish label is never truncated.
 */
export function PageHeader({ title, subtitle, action, actions, badge }: PageHeaderProps) {
  const hasActions = action !== undefined || actions !== undefined;
  return (
    <header className="mb-4 flex flex-col gap-3 border-b border-line pb-4 sm:mb-5 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="page-title min-w-0 break-words text-[22px] leading-tight text-ink sm:text-2xl">
            {title}
          </h1>
          {badge ?? null}
        </div>
        {subtitle ? (
          <p className="mt-1 line-clamp-2 text-sm text-ink-muted [overflow-wrap:anywhere]">
            {subtitle}
          </p>
        ) : null}
      </div>
      {hasActions ? (
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
          {action}
          {actions}
        </div>
      ) : null}
    </header>
  );
}
