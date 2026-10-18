import { useEffect, useRef } from "react";

/**
 * While `active` (unsaved tabs), closing or reloading the page asks the browser to confirm, and
 * same-origin link clicks to another page are held and handed to `onBlocked(to)` so the page can
 * offer Guardar / Salir sin guardar / Cancelar inline (feature 020 T083). The app has no data
 * router (no useBlocker), so the click is caught in the capture phase, before react-router's
 * Link handles it.
 */
export function useLeaveGuard(active: boolean, onBlocked: (to: string) => void): void {
  const blocked = useRef(onBlocked);
  useEffect(() => {
    blocked.current = onBlocked;
  }, [onBlocked]);

  useEffect(() => {
    if (!active) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    const intercept = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      e.preventDefault();
      e.stopPropagation();
      blocked.current(url.pathname + url.search + url.hash);
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", intercept, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", intercept, true);
    };
  }, [active]);
}
