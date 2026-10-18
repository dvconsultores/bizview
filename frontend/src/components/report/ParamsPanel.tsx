import { PanelLeftClose } from "lucide-react";
import { useCallback, useId, useState, type ReactNode } from "react";
import { IconButton } from "../IconButton";
import { useT } from "../../i18n";

export const PANEL_STORAGE_KEY = "bizview.reportPanel";

function readStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(PANEL_STORAGE_KEY) === "collapsed";
  } catch {
    return false;
  }
}

function writeStoredCollapsed(collapsed: boolean) {
  try {
    localStorage.setItem(PANEL_STORAGE_KEY, collapsed ? "collapsed" : "open");
  } catch {
    // ignore storage failures
  }
}

export function useReportPanelCollapsed(): [
  boolean,
  (collapsed: boolean) => void,
] {
  const [collapsed, setCollapsedState] = useState(readStoredCollapsed);

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next);
    writeStoredCollapsed(next);
  }, []);

  return [collapsed, setCollapsed];
}

export function ParamsPanel({
  onCollapse,
  children,
  className = "",
}: {
  onCollapse: () => void;
  children: ReactNode;
  className?: string;
}) {
  const t = useT();
  const headingId = useId();

  return (
    <aside
      aria-labelledby={headingId}
      className={`hidden lg:block lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto rounded-card border border-line bg-surface p-5 ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id={headingId} className="text-lg font-semibold text-ink">
          {t.reportParams.panelTitle}
        </h2>
        <IconButton
          icon={<PanelLeftClose className="h-5 w-5" aria-hidden />}
          aria-label={t.reportParams.collapse}
          title={t.reportParams.collapse}
          aria-expanded={true}
          onClick={onCollapse}
        />
      </div>
      <div className="mt-4">{children}</div>
    </aside>
  );
}
