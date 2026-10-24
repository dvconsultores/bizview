import { Monitor, Moon, Sun } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";
import { useT } from "../i18n";
import { THEME_PREFERENCES, type ThemePreference } from "../theme/resolve";
import { useTheme } from "../theme/ThemeContext";

const ICONS = { system: Monitor, light: Sun, dark: Moon } as const;

/** "Sistema / Claro / Oscuro" (feature 006). A radio group on its own; inside the account menu it
 * is a group of menuitemradio items, since a menu may only contain menu items.
 *
 * Feature 030: `compact` is the shared view's two-option toggle (Claro / Oscuro) beside the language
 * switcher. It starts from the device appearance and stores the viewer's choice on this device; the
 * public page never writes to an account. */
export function ThemeSwitcher({ inMenu = false, compact = false }: { inMenu?: boolean; compact?: boolean }) {
  const t = useT();
  const { preference, resolved, setPreference } = useTheme();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const options: readonly ThemePreference[] = compact ? (["light", "dark"] as const) : THEME_PREFERENCES;
  // With two options there is no "system" button: the resolved value shows which one is in force.
  const selected: ThemePreference = compact ? resolved : preference;

  // Radio-group keyboard pattern: arrows move and select (roving tabindex).
  const onKeyDown = (e: KeyboardEvent, i: number) => {
    if (inMenu) return;
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (i + step + THEME_PREFERENCES.length) % THEME_PREFERENCES.length;
    refs.current[next]?.focus();
    void setPreference(THEME_PREFERENCES[next]);
  };

  return (
    <div
      role={inMenu ? "group" : "radiogroup"}
      aria-label={t.theme.label}
      className={`${compact ? "grid w-fit grid-cols-2" : "grid-cols-3"} gap-1 rounded-xl bg-surface-2 p-1`}
    >
      {options.map((p: ThemePreference, i) => {
        const Icon = ICONS[p];
        const checked = p === selected;
        return (
          <button
            key={p}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role={inMenu ? "menuitemradio" : "radio"}
            aria-checked={checked}
            aria-label={compact ? t.theme[p] : undefined}
            tabIndex={inMenu || checked ? 0 : -1}
            onClick={() => void setPreference(p)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`flex min-h-tap min-w-tap items-center justify-center rounded-lg px-2 font-medium ${
              inMenu ? "flex-col text-xs" : "text-sm"
            } ${checked ? "bg-surface text-accent shadow-sm ring-1 ring-line" : "text-ink-muted hover:text-ink"}`}
          >
            <Icon className={`h-4 w-4 shrink-0 ${inMenu ? "mb-0.5" : compact ? "" : "mr-1.5"}`} aria-hidden />
            {compact ? null : t.theme[p]}
          </button>
        );
      })}
    </div>
  );
}
