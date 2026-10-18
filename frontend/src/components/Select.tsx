import { forwardRef, useId, type ReactNode, type SelectHTMLAttributes } from "react";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: ReactNode;
  error?: string | null;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, id, className = "", ...rest },
  ref,
) {
  const autoId = useId();
  const selectId = id ?? autoId;
  const hintId = hint ? `${selectId}-hint` : undefined;
  const errorId = error ? `${selectId}-error` : undefined;
  return (
    <div className={className}>
      <div className="mb-1.5 flex items-baseline gap-0.5">
        <label htmlFor={selectId} className="block text-sm font-semibold text-ink-2">
          {label}
        </label>
        {rest.required ? (
          <span aria-hidden="true" className="text-danger">
            *
          </span>
        ) : null}
      </div>
      <select
        ref={ref}
        id={selectId}
        aria-invalid={error ? true : undefined}
        aria-describedby={[errorId, hintId].filter(Boolean).join(" ") || undefined}
        className={`block min-h-[3.25rem] w-full rounded-xl border px-4 text-base text-ink transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
          error
            ? "border-danger-border bg-field focus:ring-danger-focus"
            : "border-transparent bg-field focus:ring-field-focus"
        }`}
        {...rest}
      />
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
