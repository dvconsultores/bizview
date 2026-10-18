import { Globe } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";
import { useLocale, useT, type LocalePreference } from "../i18n";

const FULL: readonly LocalePreference[] = ["es", "en", null];
const COMPACT: readonly LocalePreference[] = ["es", "en"];

/** "Español / English / Idioma del navegador" (feature 022, US1). Full variant on Perfil and in
 * the account menu; compact variant (Español / English only) on public pages (sign-in, shared
 * view), where the choice is stored on the device. Same radio-group / menuitemradio rules as
 * ThemeSwitcher. */
export function LanguageSwitcher({ inMenu = false, compact = false }: { inMenu?: boolean; compact?: boolean }) {
  const t = useT();
  const { locale, preference, setPreference } = useLocale();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const options = compact ? COMPACT : FULL;

  // Radio-group keyboard pattern: arrows move and select (roving tabindex).
  const onKeyDown = (e: KeyboardEvent, i: number) => {
    if (inMenu) return;
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (i + step + options.length) % options.length;
    refs.current[next]?.focus();
    void setPreference(options[next]);
  };

  return (
    <div
      role={inMenu ? "group" : "radiogroup"}
      aria-label={t.language.label}
      className={`${compact ? "grid-cols-2 w-fit" : "grid-cols-3"} grid gap-1 rounded-xl bg-surface-2 p-1`}
    >
      {options.map((p: LocalePreference, i) => {
        const checked = compact ? p === locale : p === preference;
        const label = p === null ? (inMenu ? t.language.browserShort : t.language.browser) : p === "es" ? t.language.es : t.language.en;
        return (
          <button
            key={p ?? "browser"}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role={inMenu ? "menuitemradio" : "radio"}
            aria-checked={checked}
            tabIndex={inMenu || checked ? 0 : -1}
            lang={p === null ? undefined : p}
            onClick={() => void setPreference(p)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`flex min-h-tap min-w-tap items-center justify-center rounded-lg ${compact ? "px-3" : "px-2"} font-medium ${
              inMenu ? "flex-col text-xs" : "text-sm"
            } ${checked ? "bg-surface text-accent shadow-sm ring-1 ring-line" : "text-ink-muted hover:text-ink"}`}
          >
            {p === null ? <Globe className={`h-4 w-4 shrink-0 ${inMenu ? "mb-0.5" : "mr-1.5"}`} aria-hidden /> : null}
            {label}
          </button>
        );
      })}
    </div>
  );
}
