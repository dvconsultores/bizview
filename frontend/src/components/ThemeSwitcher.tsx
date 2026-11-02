import { Monitor, Moon, Sun } from "lucide-react";
import { SegmentedControl, type SegmentedOption } from "./SegmentedControl";
import { useT } from "../i18n";
import { THEME_PREFERENCES, type ThemePreference } from "../theme/resolve";
import { useTheme } from "../theme/ThemeContext";

const ICONS = { system: Monitor, light: Sun, dark: Moon } as const;

/** "Sistema / Claro / Oscuro" (feature 006), one row wherever it appears (feature 050).
 *
 * `inMenu` renders the same choice as `menuitemradio` items, since a menu may only contain menu
 * items. `compact` is the shared view's two-option toggle (Claro / Oscuro) beside the language
 * switcher: with two options there is no "system", and the resolved value shows which one is in
 * force. The public page never writes to an account — it stores the viewer's choice on the device.
 */
export function ThemeSwitcher({ inMenu = false, compact = false }:
  { inMenu?: boolean; compact?: boolean }) {
  const t = useT();
  const { preference, resolved, setPreference } = useTheme();
  const values: readonly ThemePreference[] = compact ? (["light", "dark"] as const) : THEME_PREFERENCES;
  const options: SegmentedOption<ThemePreference>[] = values.map((value) => ({
    value, label: t.theme[value], icon: ICONS[value],
  }));
  return (
    <SegmentedControl
      options={options}
      value={compact ? resolved : preference}
      onChange={(value) => void setPreference(value)}
      label={t.theme.label}
      inMenu={inMenu}
      iconOnly={compact}
    />
  );
}
