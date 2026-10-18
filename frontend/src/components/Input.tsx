import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  trailing?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, trailing, id, className = "", ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  return (
    <div className={className}>
      <div className="mb-1.5 flex items-baseline gap-0.5">
        <label htmlFor={inputId} className="block text-sm font-semibold text-ink-2">
          {label}
        </label>
        {rest.required ? (
          <span aria-hidden="true" className="text-danger">
            *
          </span>
        ) : null}
      </div>
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={[errorId, hintId].filter(Boolean).join(" ") || undefined}
          className={`block min-h-[3.25rem] w-full rounded-xl border px-4 py-3 text-ink placeholder-ink-faint transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
            error
              ? "border-danger-border bg-field focus:ring-danger-focus"
              : "border-transparent bg-field focus:ring-field-focus"
          } ${trailing ? "pr-12" : ""}`}
          {...rest}
        />
        {trailing ? <div className="absolute right-0 top-0 flex h-full items-center pr-1">{trailing}</div> : null}
      </div>
      {error ? (
        <p id={errorId} className="mt-1.5 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {hint ? (
        <div id={hintId} className="mt-1.5 text-sm text-ink-soft">
          {hint}
        </div>
      ) : null}
    </div>
  );
});
