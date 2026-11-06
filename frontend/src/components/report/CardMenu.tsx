import { useEffect, useId, useRef, useState, type FocusEvent as ReactFocusEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { Download, Maximize2, MoreVertical } from "lucide-react";
import { useT } from "../../i18n";
import { iconButtonClass } from "../IconButton";

interface CardMenuProps {
  title: string;
  onDownloadCsv: () => void;
  /** Feature 056: the same action the card's header button offers, reachable from the menu. */
  onMaximize?: () => void;
  className?: string;
}

export function CardMenu({ title, onDownloadCsv, onMaximize, className = "" }: CardMenuProps) {
  const t = useT();
  const menuId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRef = useRef<HTMLButtonElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;

    itemRef.current?.focus();

    function onPointerDown(e: PointerEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  function closeAndRestoreFocus() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  function handleKeyDown(e: ReactKeyboardEvent) {
    if (!open) return;
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeAndRestoreFocus();
    }
  }

  function handleBlur(e: ReactFocusEvent) {
    if (!wrapperRef.current?.contains(e.relatedTarget as Node)) {
      setOpen(false);
    }
  }

  function handleAction() {
    closeAndRestoreFocus();
    onDownloadCsv();
  }

  function handleMaximize() {
    closeAndRestoreFocus();
    onMaximize?.();
  }

  return (
    <div ref={wrapperRef} className={`relative ${className}`} onKeyDown={handleKeyDown} onBlur={handleBlur}>
      <button
        ref={triggerRef}
        type="button"
        className={iconButtonClass("neutral")}
        aria-label={t.reportParams.cardMenu(title)}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <MoreVertical aria-hidden className="h-5 w-5" />
      </button>

      {open ? (
        <div
          id={menuId}
          className="absolute right-0 top-full z-20 mt-1 w-max min-w-[12rem] rounded-xl border border-line bg-surface p-1 shadow-raised"
        >
          <ul>
            {onMaximize ? (
              <li>
                <button
                  type="button"
                  onClick={handleMaximize}
                  className="flex min-h-tap w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ink-2 hover:bg-subtle hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-field-focus"
                >
                  <Maximize2 aria-hidden className="h-4 w-4 shrink-0" />
                  {t.layout.maximize(title)}
                </button>
              </li>
            ) : null}
            <li>
              <button
                ref={itemRef}
                type="button"
                onClick={handleAction}
                className="flex min-h-tap w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ink-2 hover:bg-subtle hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-field-focus"
              >
                <Download aria-hidden className="h-4 w-4 shrink-0" />
                {t.reportParams.downloadCsv}
              </button>
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
