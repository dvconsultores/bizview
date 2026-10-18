import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "danger-soft";
type Size = "md" | "sm";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-primary text-on-primary shadow-sm hover:bg-primary-hover active:bg-primary-active disabled:bg-primary/50",
  secondary:
    "border border-line bg-surface text-ink-2 hover:bg-subtle active:bg-surface-2 disabled:text-ink-faint",
  ghost: "bg-transparent text-accent hover:bg-accent-soft active:bg-accent-soft-2 disabled:text-ink-faint",
  danger: "bg-danger-solid text-on-primary shadow-sm hover:bg-danger-solid-hover active:bg-danger-solid-active disabled:bg-danger-solid/50",
  // Destructive, without shouting: for toolbars where a solid red block would dominate the row.
  "danger-soft": "text-danger-strong hover:bg-danger-soft active:bg-danger-soft disabled:text-ink-faint",
};

/** Compact controls for a toolbar: 36 px with a mouse, 44 px under a finger (see `control-compact`). */
const SIZES: Record<Size, string> = {
  md: "px-4 text-base font-semibold rounded-xl",
  sm: "control-compact rounded-lg px-3 text-sm font-medium [&_svg]:h-4 [&_svg]:w-4",
};

export function buttonClass(variant: Variant = "primary", block: boolean = false,
                            className: string = "", size: Size = "md"): string {
  return `inline-flex items-center justify-center transition-colors disabled:cursor-not-allowed ${
    size === "md" ? "min-h-tap" : ""
  } ${SIZES[size]} ${block ? "w-full" : ""} ${VARIANTS[variant]} ${className}`;
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
  block?: boolean;
}

/** Min 44 px tall; while `loading` it is disabled so repeated taps are ignored (FR-029). */
export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  block = false,
  className = "",
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass(variant, block, className, size)}
      {...rest}
    >
      {loading ? (
        <Spinner className={size === "sm" ? "mr-1.5 h-4 w-4" : "mr-2 h-5 w-5"} />
      ) : icon ? (
        <span className={size === "sm" ? "mr-1.5 inline-flex" : "mr-2 inline-flex"}>{icon}</span>
      ) : null}
      {children}
    </button>
  );
}

export interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  icon?: ReactNode;
  block?: boolean;
}

export function ButtonLink({ variant = "primary", icon, block = false, className = "", children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, block, className)} {...rest}>
      {icon ? <span className="mr-2 inline-flex">{icon}</span> : null}
      {children}
    </Link>
  );
}
