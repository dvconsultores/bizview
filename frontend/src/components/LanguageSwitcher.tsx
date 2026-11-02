import { Globe } from "lucide-react";
import { SegmentedControl, type SegmentedOption } from "./SegmentedControl";
import { useLocale, useT, type LocalePreference } from "../i18n";

const FULL: readonly LocalePreference[] = ["es", "en", null];
const COMPACT: readonly LocalePreference[] = ["es", "en"];

/** "Español / English / Idioma del navegador" (feature 022), the same control as the theme choice
 * (feature 050). Full variant on Perfil and in the account menu; compact variant on public pages
 * (sign-in, shared view), where the choice is stored on the device. */
export function LanguageSwitcher({ inMenu = false, compact = false }:
  { inMenu?: boolean; compact?: boolean }) {
  const t = useT();
  const { locale, preference, setPreference } = useLocale();
  const values = compact ? COMPACT : FULL;
  const options: SegmentedOption<string>[] = values.map((value) => ({
    value: value ?? "browser",
    label: value === null
      ? (inMenu ? t.language.browserShort : t.language.browser)
      : value === "es" ? t.language.es : t.language.en,
    // The full variant is three equal columns on a phone: an icon beside "Idioma del navegador"
    // leaves the word too little room, so the label stands alone there. The compact and in-menu
    // variants keep the globe, where the label is one word.
    icon: value === null && (compact || inMenu) ? Globe : undefined,
    lang: value ?? undefined,
  }));
  return (
    <SegmentedControl
      options={options}
      // With the "browser" option, no preference means that option is the choice; without it
      // (compact), the resolved language is what the reader is actually seeing.
      value={compact ? locale : preference ?? "browser"}
      onChange={(value) => void setPreference(value === "browser" ? null : value as "es" | "en")}
      label={t.language.label}
      inMenu={inMenu}
    />
  );
}
