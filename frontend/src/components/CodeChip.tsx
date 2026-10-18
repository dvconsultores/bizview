import type { ReactNode } from "react";

export interface CodeChipProps {
  children: ReactNode;
  className?: string;
  title?: string;
}

export function CodeChip({ children, className = "", title }: CodeChipProps) {
  return (
    <code
      title={title}
      className={`inline-flex max-w-full items-center rounded-lg border border-line bg-subtle px-2 py-0.5 font-mono text-xs font-semibold text-ink-2 break-all ${className}`}
    >
      {children}
    </code>
  );
}
