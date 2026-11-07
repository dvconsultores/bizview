import { useCallback, useEffect, useId, useRef, type ReactNode } from "react";
import { ArrowLeft, ArrowRight, Download, Image as ImageIcon, X } from "lucide-react";
import { useT } from "../../i18n";

/**
 * Feature 056: one dashboard card, full screen.
 *
 * The product has no ad-hoc modals (see `no-modals.test.ts`); this is the single, deliberate
 * exception, and the guard names it. It exists because a chart needs width: the same component is
 * rendered again at the viewport's size, so every label fits and the bars are taller.
 */
export function CardDialog({
  open,
  title,
  caption,
  period,
  comparison,
  filters,
  onClose,
  onPrevious,
  onNext,
  onDownloadCsv,
  onDownloadPng,
  children,
}: {
  open: boolean;
  title: string;
  caption?: string;
  /** Feature 056b: read in the dialog — the period, the comparison and the active filters. */
  period?: string;
  comparison?: string;
  filters?: string[];
  onClose: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
  onDownloadCsv?: () => void;
  onDownloadPng?: () => void;
  children: ReactNode;
}) {
  const t = useT();
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const onKeyDown = useCallback((event: KeyboardEvent) => {
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "ArrowLeft" && onPrevious) {
      event.preventDefault();
      onPrevious();
      return;
    }
    if (event.key === "ArrowRight" && onNext) {
      event.preventDefault();
      onNext();
    }
  }, [open, onClose, onPrevious, onNext]);

  useEffect(() => {
    if (!open) return;
    const node = panel.current;
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    document.addEventListener("keydown", onKeyDown);
    // Focus stays inside the card while it is open (FR-008).
    const trap = (event: FocusEvent) => {
      if (!node || node.contains(event.target as Node)) return;
      closeRef.current?.focus();
    };
    document.addEventListener("focusin", trap);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("focusin", trap);
      previous?.focus?.();
    };
  }, [open, onKeyDown]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-ink/50 p-0 sm:p-6"
         onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId}
           data-card-dialog=""
           className="flex h-full w-full max-w-[92rem] flex-col overflow-hidden bg-surface sm:rounded-card sm:shadow-raised">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-lg font-semibold text-ink [overflow-wrap:anywhere]">
              {title}
            </h2>
            {period || comparison || (filters && filters.length > 0) ? (
              <ul className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted"
                  data-dialog-meta="">
                {period ? (
                  <li className="rounded-full bg-subtle px-2 py-0.5 font-medium text-ink-2">{period}</li>
                ) : null}
                {comparison ? (
                  <li className="rounded-full bg-subtle px-2 py-0.5 font-medium text-ink-2">{comparison}</li>
                ) : null}
                {(filters ?? []).map((chip) => (
                  <li key={chip} className="rounded-full border border-line px-2 py-0.5 [overflow-wrap:anywhere]">
                    {chip}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          {onPrevious ? (
            <button type="button" onClick={onPrevious} aria-label={t.layout.previousCard}
                    className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-ink-2 hover:bg-subtle">
              <ArrowLeft className="h-5 w-5" aria-hidden />
            </button>
          ) : null}
          {onNext ? (
            <button type="button" onClick={onNext} aria-label={t.layout.nextCard}
                    className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-ink-2 hover:bg-subtle">
              <ArrowRight className="h-5 w-5" aria-hidden />
            </button>
          ) : null}
          {onDownloadCsv ? (
            <button type="button" onClick={onDownloadCsv}
                    className="inline-flex min-h-tap items-center gap-1.5 rounded-btn px-3 text-sm font-semibold text-ink-2 hover:bg-subtle">
              <Download className="h-4 w-4" aria-hidden />{t.reportParams.downloadCsv}
            </button>
          ) : null}
          {onDownloadPng ? (
            <button type="button" onClick={onDownloadPng}
                    className="inline-flex min-h-tap items-center gap-1.5 rounded-btn px-3 text-sm font-semibold text-ink-2 hover:bg-subtle">
              <ImageIcon className="h-4 w-4" aria-hidden />{t.layout.downloadPng}
            </button>
          ) : null}
          <button ref={closeRef} type="button" onClick={onClose} aria-label={t.layout.closeMaximized}
                  className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-ink-2 hover:bg-subtle">
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>
        <div data-card-dialog-body="" className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">{children}</div>
        {caption ? (
          <p className="border-t border-line px-4 py-2 text-xs text-ink-muted [overflow-wrap:anywhere]">{caption}</p>
        ) : null}
      </div>
    </div>
  );
}
