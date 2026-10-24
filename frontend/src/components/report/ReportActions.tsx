import { MoreHorizontal, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useT } from "../../i18n";
import { Button } from "../Button";
import { iconButtonClass } from "../IconButton";

export interface ReportAction {
  id: string;
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  /** Hidden when false (e.g. Compartir on a report with no dashboard). */
  show: boolean;
  loading?: boolean;
}

interface ReportActionsProps {
  activeFilters: number;
  onOpenFilters: () => void;
  onOpenParams: () => void;
  /** Everything that can collapse into "⋯" below 640 px, in order. */
  actions: ReportAction[];
  /** How many leading actions never collapse (the shared view has a single one: the PDF). */
  alwaysVisible?: number;
}

/**
 * Feature 030 (FR-005, US2.3; owner 2026-10-24): a small control, not a toolbar. Filtros and
 * Parámetros show icon + label; every other action lives in the "⋯" menu at every width, so the row
 * is three controls and the dashboard keeps its room. Keyboard reachable (menu with roving focus,
 * Esc closes and returns focus), 44 px targets, `data-sheet-opener` so the sheet's outside-click does
 * not swallow the button that opens it.
 */
export function ReportActions({
  activeFilters,
  onOpenFilters,
  onOpenParams,
  actions,
  alwaysVisible = 0,
}: ReportActionsProps) {
  const t = useT();
  const visible = actions.filter((action) => action.show);
  const pinned = visible.slice(0, alwaysVisible);
  const collapsed = visible.slice(alwaysVisible);
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  useEffect(() => {
    if (open) menuRef.current?.querySelector<HTMLElement>("[role='menuitem']")?.focus();
  }, [open]);

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="report-actions">
      <span data-sheet-opener className="contents">
        <Button
          variant="secondary"
          icon={<SlidersHorizontal className="h-5 w-5" aria-hidden />}
          onClick={onOpenFilters}
          aria-label={t.reportActions.filters(activeFilters)}
        >
          {t.reportActions.filters(activeFilters)}
        </Button>
      </span>
      <span data-sheet-opener className="contents">
        <Button
          variant="secondary"
          icon={<SlidersHorizontal className="h-5 w-5" aria-hidden />}
          onClick={onOpenParams}
          aria-label={t.reportActions.params}
        >
          {t.reportActions.params}
        </Button>
      </span>

      {pinned.length > 0 ? (
      <div className="flex items-center gap-2">
        {pinned.map((action) => {
          const Icon = action.icon;
          return (
            <Button
              key={action.id}
              variant="secondary"
              loading={action.loading}
              icon={<Icon className="h-5 w-5" aria-hidden />}
              onClick={action.onClick}
            >
              {action.label}
            </Button>
          );
        })}
      </div>
      ) : null}

      <div className={collapsed.length > 0 ? "relative" : "hidden"} ref={menuRef}>
        <button
          ref={triggerRef}
          type="button"
          aria-label={t.reportActions.more}
          aria-haspopup="menu"
          aria-expanded={open}
          className={iconButtonClass()}
          onClick={() => setOpen((value) => !value)}
        >
          <MoreHorizontal className="h-5 w-5" aria-hidden />
        </button>
        {open ? (
          <div
            role="menu"
            aria-label={t.reportActions.more}
            className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-line bg-surface p-1 shadow-raised"
          >
            {collapsed.map((action) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.id}
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpen(false);
                    action.onClick();
                  }}
                  className="flex min-h-tap w-full items-center rounded-lg px-3 text-left text-sm font-medium text-ink hover:bg-subtle"
                >
                  <Icon className="mr-2 h-5 w-5 shrink-0" aria-hidden />
                  {action.label}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
