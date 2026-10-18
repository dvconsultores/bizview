import type { ReactNode } from "react";

type Tone = "blue" | "green" | "gray" | "red" | "amber" | "accent" | "success" | "neutral" | "danger" | "warning";

const ALIAS: Record<Exclude<Tone, "blue" | "green" | "gray" | "red" | "amber">, string> = {
  accent: "blue",
  success: "green",
  neutral: "gray",
  danger: "red",
  warning: "amber",
};

const TONES: Record<"blue" | "green" | "gray" | "red" | "amber", string> = {
  blue: "bg-accent-soft text-accent ring-accent-line",
  green: "bg-success-soft text-success ring-success-line",
  gray: "bg-surface-2 text-ink-3 ring-line",
  red: "bg-danger-soft text-danger ring-danger-line",
  amber: "bg-warning-soft text-warning-deep ring-warning-line",
};

export interface BadgeProps {
  tone?: Tone;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
  wrap?: boolean;
}

export function Badge({ tone = "gray", icon, className = "", children, wrap = false }: BadgeProps) {
  const resolved = tone in ALIAS ? ALIAS[tone as keyof typeof ALIAS] : tone;
  const wrapClasses = wrap
    ? "whitespace-normal max-w-full break-words [overflow-wrap:anywhere] text-left"
    : "whitespace-nowrap";
  return (
    <span
      className={`inline-flex items-center ${wrapClasses} rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${
        TONES[resolved as keyof typeof TONES]
      } ${className}`}
    >
      {icon ? <span className="mr-1 inline-flex">{icon}</span> : null}
      {children}
    </span>
  );
}
