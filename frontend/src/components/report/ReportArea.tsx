import type { CSSProperties, ReactNode } from "react";
import { themeStyle } from "../../theme/palette";
import type { Theme, ThemeMode } from "../../theme/themes";

/** The block that renders a report's own content, painted from the report's theme and mode.
 *
 * Feature 047 FR-019: the theme and the mode belong to the report, not to the application. Scoping
 * the custom properties here is what lets `mode: dark` turn a dark report inside a light
 * application without touching the chrome around it. */
export function ReportArea({
  theme,
  mode,
  className = "",
  children,
  ...rest
}: {
  theme: Theme;
  mode: ThemeMode;
  className?: string;
  children: ReactNode;
  "aria-busy"?: boolean;
  inert?: boolean;
}) {
  return (
    <div
      {...rest}
      className={className}
      style={themeStyle(theme, mode) as CSSProperties}
      data-report-mode={mode}
      data-report-theme={theme.id}
    >
      {children}
    </div>
  );
}
