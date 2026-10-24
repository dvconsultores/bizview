import { X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, type ReactNode } from "react";
import { useT } from "../../i18n";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ReportSheetProps {
  open: boolean;
  /** Names the panel ("Filtros"); the dashboard keeps its own numbers visible beside it. */
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Rendered under the content ("Listo"). */
  footer?: ReactNode;
}

/**
 * Feature 030 (FR-003): one non-blocking sheet for filters and parameters. A right side sheet from
 * 1024 px (360 px, no backdrop, the dashboard stays interactive) and a bottom sheet below it (drag
 * handle, 70% height, swipe or Esc to close). It is a landmark `region` with its own heading — never
 * a dialog, per the app's no-modals rule (`tests/unit/no-modals.test.ts`): focus moves in and cycles
 * while it is open, Esc closes it and returns focus to the opener, and the page behind stays usable.
 */
export function ReportSheet({ open, title, onClose, children, footer }: ReportSheetProps) {
  const t = useT();
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const dragRef = useRef<number | null>(null);
  const titleId = useId();

  const close = useCallback(() => {
    onClose();
    openerRef.current?.focus?.();
    openerRef.current = null;
  }, [onClose]);

  // Remembers the opener so closing can return focus to it (FR-003).
  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();
  }, [open]);

  // Esc closes, Tab cycles inside while the sheet is open, and a click outside closes it on desktop.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        event.preventDefault();
        last.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      if (panelRef.current?.contains(target)) return;
      if (target.closest("[data-sheet-opener]")) return;
      if (window.matchMedia?.("(min-width: 1024px)").matches) close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, close]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      role="region"
      aria-labelledby={titleId}
      data-testid="report-sheet"
      onTouchStart={(event) => {
        dragRef.current = event.touches[0]?.clientY ?? null;
      }}
      onTouchMove={(event) => {
        if (dragRef.current === null) return;
        const dy = (event.touches[0]?.clientY ?? 0) - dragRef.current;
        if (dy > 70) {
          dragRef.current = null;
          close();
        }
      }}
      onTouchEnd={() => {
        dragRef.current = null;
      }}
      className="fixed inset-x-0 bottom-0 z-40 flex max-h-[70vh] flex-col rounded-t-2xl border-t border-line bg-surface shadow-raised outline-none transition-transform duration-200 ease-out motion-reduce:transition-none lg:inset-y-0 lg:left-auto lg:right-0 lg:max-h-none lg:w-[360px] lg:rounded-none lg:border-l lg:border-t-0"
    >
      <div aria-hidden className="mx-auto mt-2 h-1.5 w-10 shrink-0 rounded-full bg-line-strong lg:hidden" />
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <h2 id={titleId} className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
          {title}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t.reportSheet.close}
          className="min-h-tap min-w-tap shrink-0 rounded-lg text-ink-muted hover:text-ink"
        >
          <X className="mx-auto h-5 w-5" aria-hidden />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
      <div className="shrink-0 border-t border-line px-4 py-3 pb-safe">
        {footer ?? (
          <button
            type="button"
            onClick={close}
            className="min-h-tap w-full rounded-xl bg-primary px-4 font-semibold text-on-primary"
          >
            {t.reportSheet.done}
          </button>
        )}
      </div>
    </div>
  );
}
