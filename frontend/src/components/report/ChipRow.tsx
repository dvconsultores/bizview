import type { ReactNode } from "react";

export interface ChipOption {
  /** `""` is the "installation default" option of the palette row, so it is a valid id. */
  id: string;
  label: string;
  /** Optional decoration before the label (swatches, icons). */
  visual?: ReactNode;
}

interface ChipRowProps {
  label: string;
  options: readonly ChipOption[];
  value: string;
  onChange: (id: string) => void;
  /** Announced as the group's name; defaults to `label`, which is also painted above the row. */
  labelHidden?: boolean;
  testId?: string;
}

/**
 * Feature 059: the single-line chip row the phone sheet uses instead of a `<select>` for short
 * lists (palette, theme, refresh cadence). It scrolls horizontally, keeps a 44 px target and
 * announces the choice with `aria-pressed` inside a labelled group, so a screen reader hears the
 * same thing the `<select>` said on a wide screen.
 */
export function ChipRow({ label, options, value, onChange, labelHidden = false, testId }: ChipRowProps) {
  return (
    <div data-testid={testId}>
      <p className={labelHidden ? "sr-only" : "mb-1.5 text-sm font-semibold text-ink-2"}>{label}</p>
      <div
        role="group"
        aria-label={label}
        className="-mx-1 flex snap-x items-center gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {options.map((option) => {
          const selected = option.id === value;
          return (
            <button
              key={option.id || "default"}
              type="button"
              aria-pressed={selected}
              onClick={() => onChange(option.id)}
              className={`flex min-h-tap shrink-0 snap-start items-center gap-1.5 rounded-full border px-3 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
                selected
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line bg-surface text-ink-2 hover:bg-subtle hover:text-ink"
              }`}
            >
              {option.visual}
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
