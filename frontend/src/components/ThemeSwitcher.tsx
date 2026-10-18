import { Monitor, Moon, Sun } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";
import { useT } from "../i18n";
import { THEME_PREFERENCES, type ThemePreference } from "../theme/resolve";
import { useTheme } from "../theme/ThemeContext";

const ICONS = { system: Monitor, light: Sun, dark: Moon } as const;

/** "Sistema / Claro / Oscuro" (feature 006). A radio group on its own; inside the account menu it
 * is a group of menuitemradio items, since a menu may only contain menu items. */
export function ThemeSwitcher({ inMenu = false }: { inMenu?: boolean }) {
  const t = useT();
  const { preference, setPreference } = useTheme();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

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
      className="grid grid-cols-3 gap-1 rounded-xl bg-surface-2 p-1"
    >
      {THEME_PREFERENCES.map((p: ThemePreference, i) => {
        const Icon = ICONS[p];
        const checked = p === preference;
        return (
          <button
            key={p}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role={inMenu ? "menuitemradio" : "radio"}
            aria-checked={checked}
            tabIndex={inMenu || checked ? 0 : -1}
            onClick={() => void setPreference(p)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`flex min-h-tap min-w-tap items-center justify-center rounded-lg px-2 font-medium ${
              inMenu ? "flex-col text-xs" : "text-sm"
            } ${checked ? "bg-surface text-accent shadow-sm ring-1 ring-line" : "text-ink-muted hover:text-ink"}`}
          >
            <Icon className={`h-4 w-4 shrink-0 ${inMenu ? "mb-0.5" : "mr-1.5"}`} aria-hidden />
            {t.theme[p]}
          </button>
        );
      })}
    </div>
  );
}
