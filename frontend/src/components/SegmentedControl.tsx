import { useRef, type ComponentType, type KeyboardEvent } from "react";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  /** The language of the label, when the option is a language (`lang="es"`). */
  lang?: string;
}

export interface SegmentedControlProps<T extends string> {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  /** The group's accessible name. */
  label: string;
  /** Inside a menu the children must be `menuitemradio`; outside it they are `radio`. */
  inMenu?: boolean;
  /** Only the icons, for a narrow surface. The label stays as the accessible name. */
  iconOnly?: boolean;
}

/** Two or three options cover every control in the product; more falls back to an inline template. */
const COLUMNS: Record<number, string> = { 2: "grid-cols-2", 3: "grid-cols-3" };

/**
 * One mutually-exclusive choice, in one row (feature 050, evidence 3 and 4).
 *
 * The theme and language switches used to be two hand-written copies, and one of them emitted
 * `grid-cols-3` without `grid` — so "Sistema / Claro / Oscuro" stacked vertically while the language
 * options sat in a row. The layout is a property of this component now, so the two cannot answer
 * differently again.
 *
 * Keyboard follows the radio-group pattern: one tab stop (the selected option), arrows move and
 * select. Inside a menu the children are `menuitemradio` and the menu owns the keys, so `tabIndex`
 * is left at 0 and `onKeyDown` is not attached.
 */
export function SegmentedControl<T extends string>({
  options, value, onChange, label, inMenu = false, iconOnly = false,
}: SegmentedControlProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));

  const onKeyDown = (e: KeyboardEvent, index: number) => {
    if (inMenu) return;
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1
      : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (index + step + options.length) % options.length;
    refs.current[next]?.focus();
    onChange(options[next].value);
  };

  return (
    <div
      role={inMenu ? "group" : "radiogroup"}
      aria-label={label}
      data-segmented=""
      className={`grid w-fit gap-1 rounded-xl bg-surface-2 p-1 ${
        COLUMNS[options.length] ?? ""}`}
      style={COLUMNS[options.length] ? undefined
        : { gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map((option, index) => {
        const Icon = option.icon;
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            ref={(el) => { refs.current[index] = el; }}
            type="button"
            role={inMenu ? "menuitemradio" : "radio"}
            aria-checked={checked}
            aria-label={iconOnly ? option.label : undefined}
            lang={option.lang}
            tabIndex={inMenu || checked ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(e) => onKeyDown(e, index)}
            className={`flex min-h-tap min-w-tap items-center justify-center gap-1.5 rounded-lg px-2.5 text-sm font-medium ${
              inMenu ? "flex-col gap-0.5 px-2 text-xs" : ""
            } ${checked
              ? "bg-surface text-accent shadow-sm ring-1 ring-line"
              : "text-ink-muted hover:text-ink"}`}
          >
            {Icon ? <Icon className="h-4 w-4 shrink-0" aria-hidden /> : null}
            {/* A translated label wraps at its spaces rather than carrying an ellipsis: "Idioma del
                navegador" is three words in a third of a phone, and a truncated primary choice
                reads as a bug. It never breaks inside a word. */}
            {iconOnly ? null : (
              <span className="min-w-0 text-center leading-tight">{option.label}</span>
            )}
          </button>
        );
      })}
      {/* Keeps the last tab position meaningful when the selection is the last option. */}
      <span className="sr-only" aria-live="polite">
        {options[selectedIndex]?.label ?? ""}
      </span>
    </div>
  );
}
