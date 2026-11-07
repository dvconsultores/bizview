import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

/**
 * Feature 056b: the value chip follows the pointer, clamped inside the card.
 *
 * Feature 056 anchored it to the mark, which reads as a label rather than a tooltip; the spec asks
 * for a chip that follows the pointer and never leaves the card. The position is kept relative to
 * the chart's own box, so the caller only clamps against the width and height it already draws in.
 */
export function usePointerChip() {
  const ref = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    setAt({ x: event.clientX - rect.left, y: event.clientY - rect.top });
  };
  const onPointerLeave = () => setAt(null);

  /** Where to draw a chip of `w × h` at the pointer, kept inside `width × height`. */
  const place = (width: number, height: number, w = 190, h = 0) => {
    if (!at) return null;
    return {
      left: Math.max(4, Math.min(at.x + 12, Math.max(4, width - w - 4))),
      top: Math.max(0, Math.min(at.y + 16, Math.max(0, height - h - 4))),
    };
  };

  return { ref, at, onPointerMove, onPointerLeave, place };
}
