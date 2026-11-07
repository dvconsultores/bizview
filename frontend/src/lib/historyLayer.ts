import { useEffect, useRef } from "react";

/**
 * Popstate events we caused ourselves, so they never close a layer. Browsers (and jsdom) deliver
 * the traversal asynchronously: the entry may be gone by the time the event arrives, and a newer
 * layer would take it as a back press.
 */
let selfPops = 0;

/** The state we push when a layer (the report sheet) opens. */
interface LayerState {
  bizviewLayer?: string;
}

/**
 * Feature 059: a full-screen surface answers the phone's back button.
 *
 * Opening pushes one history entry; `popstate` (the back button, or `history.back()`) closes the
 * layer. A close from the UI calls `history.back()` when our entry is still current — so the stack
 * does not grow — and closes directly otherwise (somebody already navigated).
 *
 * The layer is identified by `key` so two sheets on the same page never steal each other's entry.
 */
export function useHistoryLayer(open: boolean, onClose: () => void, key = "sheet"): void {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const pushed = useRef(false);

  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    const state = (window.history.state ?? {}) as LayerState;
    if (state.bizviewLayer !== key) {
      window.history.pushState({ ...state, bizviewLayer: key }, "");
    }
    pushed.current = true;
    const onPop = () => {
      if (selfPops > 0) {
        selfPops -= 1;
        return;
      }
      if (!pushed.current) return;
      pushed.current = false;
      closeRef.current();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      if (!pushed.current) return;
      pushed.current = false;
      const current = (window.history.state ?? {}) as LayerState;
      // Closing from the UI: give the entry back instead of leaving a dead stop in the history.
      if (current.bizviewLayer === key) {
        selfPops += 1;
        window.history.back();
      }
    };
  }, [open, key]);
}
