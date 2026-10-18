import { useEffect, useId, useRef, useState, type FocusEvent as ReactFocusEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { Download, MoreVertical } from "lucide-react";
import { useT } from "../../i18n";
import { iconButtonClass } from "../IconButton";

interface CardMenuProps {
  title: string;
  onDownloadCsv: () => void;
  className?: string;
}

export function CardMenu({ title, onDownloadCsv, className = "" }: CardMenuProps) {
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
