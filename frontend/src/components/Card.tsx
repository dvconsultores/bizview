import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  tone?: "plain" | "accent";
}

export function Card({ tone = "plain", className = "", ...rest }: CardProps) {
  const border = tone === "accent" ? "border-line-accent" : "border-line";
  return (
    <div className={`card-surface rounded-card border bg-surface ${border} ${className}`} {...rest} />
  );
}
