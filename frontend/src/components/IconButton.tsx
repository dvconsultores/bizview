import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";

type Tone = "neutral" | "danger";

interface BaseProps {
  icon: ReactNode;
  tone?: Tone;
  className?: string;
  "aria-label": string;
  title?: string;
}

type ButtonProps = BaseProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "aria-label"> & {
    to?: undefined;
  };

type LinkButtonProps = BaseProps &
  Omit<LinkProps, "children" | "aria-label"> & {
    to: string;
  };

type IconButtonProps = ButtonProps | LinkButtonProps;

export function iconButtonClass(tone: Tone = "neutral", className = ""): string {
  const base =
    "inline-flex h-11 w-11 min-h-tap min-w-tap shrink-0 items-center justify-center rounded-xl transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-field-focus disabled:cursor-not-allowed disabled:opacity-60";
  const toneClass =
    tone === "danger"
      ? "text-danger hover:bg-danger-soft"
      : "text-ink-muted hover:bg-subtle hover:text-accent";
  return `${base} ${toneClass} ${className}`.trim();
}

/** 44 px icon-only action (feature 010, admin table rows). `aria-label` is required. */
export function IconButton(props: IconButtonProps) {
  const { icon, tone = "neutral", className = "", title, "aria-label": ariaLabel, ...rest } = props;
  const resolvedTitle = title ?? ariaLabel;
  const classes = iconButtonClass(tone, className);

  if ("to" in props && props.to !== undefined) {
    const { to, ...linkRest } = rest as Omit<LinkButtonProps, keyof BaseProps>;
    return (
      <Link to={to} className={classes} aria-label={ariaLabel} title={resolvedTitle} {...linkRest}>
        {icon}
      </Link>
    );
  }

  const buttonRest = rest as ButtonHTMLAttributes<HTMLButtonElement>;
  return (
    <button type="button" className={classes} aria-label={ariaLabel} title={resolvedTitle} {...buttonRest}>
      {icon}
    </button>
  );
}
