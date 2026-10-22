import { useCallback, useEffect, useRef, type KeyboardEvent, type PointerEvent } from "react";
import { useT } from "../../i18n";
import { clampPanelWidth, PANEL_WIDTH } from "./AssistantPanelContext";

const STEP = 24;          // arrow keys
const BIG_STEP = 96;      // Shift + arrow

/**
 * The seam between the page and the docked chat, draggable like the divider of an editor
 * (owner, 2026-10-21: "make the chat that a user can resize like vs code"). The panel is on the
 * right, so dragging left makes it wider. Double-click or Enter restores the default width.
 *
 * It is the visual seam itself (`w-1.5`, the same strip the IDE puts between the explorer and the
 * editor), so nothing new appears on screen: it only reacts to the pointer and to the keyboard.
 */
export function PanelResizer({
  width,
  onResize,
  label,
}: {
  width: number;
  onResize: (px: number) => void;
  label: string;
}) {
  const t = useT();
  const drag = useRef<{ startX: number; startWidth: number } | null>(null);

  const move = useCallback(
    (clientX: number) => {
      const current = drag.current;
      if (!current) return;
      onResize(clampPanelWidth(current.startWidth + (current.startX - clientX)));
    },
    [onResize],
  );

  useEffect(() => {
    const onMove = (e: globalThis.PointerEvent) => move(e.clientX);
    const onUp = () => {
      drag.current = null;
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [move]);

  const start = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    drag.current = { startX: e.clientX, startWidth: width };
    // While dragging, the pointer stays a resize arrow everywhere and nothing gets selected.
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? BIG_STEP : STEP;
    // The panel grows to the left, so ArrowLeft widens it — the same direction as the drag.
    if (e.key === "ArrowLeft") onResize(clampPanelWidth(width + step));
    else if (e.key === "ArrowRight") onResize(clampPanelWidth(width - step));
    else if (e.key === "Home") onResize(clampPanelWidth(PANEL_WIDTH.min));
    else if (e.key === "End") onResize(clampPanelWidth(PANEL_WIDTH.max));
    else if (e.key === "Enter" || e.key === " ") onResize(PANEL_WIDTH.default);
    else return;
    e.preventDefault();
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuemin={PANEL_WIDTH.min}
      aria-valuemax={PANEL_WIDTH.max}
      aria-valuenow={Math.round(width)}
      aria-valuetext={t.assistant.panelWidth.replace("{px}", String(Math.round(width)))}
      tabIndex={0}
      data-assistant-resizer=""
      onPointerDown={start}
      onDoubleClick={() => onResize(PANEL_WIDTH.default)}
      onKeyDown={onKeyDown}
      className="absolute inset-y-0 left-0 z-10 w-1.5 cursor-col-resize touch-none bg-line hover:bg-line-accent focus-visible:bg-line-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus motion-reduce:transition-none"
    />
  );
}
