/** Accessible on/off switch with a 44 px tap target. */
export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex min-h-tap min-w-tap shrink-0 items-center justify-center disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className={`relative inline-block h-7 w-12 rounded-full transition-colors ${checked ? "bg-primary" : "bg-line-strong"}`}>
        <span
          className={`absolute left-1 top-1 h-5 w-5 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  );
}
