import type { ReactNode } from "react";

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border-2 border-dashed border-line bg-surface px-6 py-10 text-center">
      {icon ? <div className="mb-3 rounded-full bg-accent-soft p-3 text-accent-bright">{icon}</div> : null}
      <p className="font-semibold text-ink-2">{title}</p>
      {children ? <div className="mt-1 text-sm text-ink-soft">{children}</div> : null}
    </div>
  );
}
