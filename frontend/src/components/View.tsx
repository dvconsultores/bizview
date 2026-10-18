import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { ArrowLeft } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { useT } from "../i18n";
import {
  getOpenHistoryTokens,
  registerView,
  setViewHistoryToken,
  unregisterView,
  useTopHost,
  useTopViewId,
} from "./ViewHost";

function newToken(): string {
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = new Uint8Array(8);
    crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  return Math.random().toString(16).slice(2).padEnd(16, "0").slice(0, 16);
}

interface ViewProps {
  /** Whether the view is open. */
  open: boolean;
  /** The heading displayed in the view header. */
  title: string;
  /** Called for cancel, back navigation, browser/phone back, and Escape. */
  onClose: () => void;
  /** View content. */
  children: ReactNode;
  /** Optional action buttons rendered at the bottom of the view. */
  footer?: ReactNode;
  /**
   * When true, focus the first focusable field when the view opens.
   * Otherwise the heading receives focus.
   */
  autoFocus?: boolean;
}

/**
 * A full-page replacement for modal dialogs.
 *
 * The view renders in the normal document flow inside the innermost
 * `ViewHost` and participates in history so browser/phone back closes it.
 */
export function View({
  open,
  title,
  onClose,
  children,
  footer,
  autoFocus = false,
}: ViewProps): ReturnType<typeof createPortal> | null {
  const t = useT();
  const id = useId();
  const titleId = useId();
  const topHost = useTopHost();
  const topViewId = useTopViewId();
  const navigate = useNavigate();
  const location = useLocation();

  const hostKey = topHost?.key ?? null;

  const sectionRef = useRef<HTMLElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const onCloseRef = useRef(onClose);
  const tokenRef = useRef<string | null>(null);
  const pushedRef = useRef(false);
  const seenRef = useRef(false);
  const openCycleRef = useRef(false);
  const focusedRef = useRef(false);
  const savedFocusRef = useRef<HTMLElement | null>(null);
  const savedScrollYRef = useRef(0);

  // Keep the latest onClose available synchronously for Escape/back handlers.
  useLayoutEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  const isTop = open && hostKey !== null && topViewId === id;

  // Register/unregister the view with the host store.
  useEffect(() => {
    if (!open || hostKey === null) return;

    registerView(id, hostKey, tokenRef.current ?? undefined);
    return () => {
      unregisterView(id);
    };
  }, [open, hostKey, id]);

  // Push a history entry when the view opens.
  useEffect(() => {
    if (!open || hostKey === null) return;
    if (pushedRef.current) return;

    if (!tokenRef.current) {
      tokenRef.current = `${id}:${newToken()}`;
    }

    const token = tokenRef.current;
    setViewHistoryToken(id, token);

    const rawState = location.state as Record<string, unknown> | null;
    const currentViewIds = Array.isArray(rawState?.view)
      ? (rawState.view as string[])
      : [];

    const live = new Set(getOpenHistoryTokens());
    const kept = currentViewIds.filter(
      (existingToken) => live.has(existingToken) && existingToken !== token,
    );

    navigate(
      {
        pathname: location.pathname,
        search: location.search,
        hash: location.hash,
      },
      {
        state: {
          ...(rawState ?? {}),
          view: [...kept, token],
        },
      },
    );

    pushedRef.current = true;
    seenRef.current = false;
    // Intentionally no cleanup reset: strict-mode double-invocation must not
    // push a second history entry.
  }, [
    open,
    hostKey,
    id,
    location.pathname,
    location.search,
    location.hash,
    location.state,
    navigate,
  ]);

  // Watch the location for this view's token while it is open.
  useEffect(() => {
    if (!open) return;
    if (!pushedRef.current) return;
    if (tokenRef.current === null) return;

    const token = tokenRef.current;
    const rawState = location.state as Record<string, unknown> | null;
    const viewIds = Array.isArray(rawState?.view)
      ? (rawState.view as string[])
      : [];

    if (viewIds.includes(token)) {
      seenRef.current = true;
      return;
    }

    if (seenRef.current) {
      pushedRef.current = false;
      seenRef.current = false;
      tokenRef.current = null;
      onCloseRef.current();
    }
  }, [open, id, location.state]);

  // Handle the parent closing the view from the UI.
  useEffect(() => {
    if (open) return;
    if (!pushedRef.current) return;

    const token = tokenRef.current;
    pushedRef.current = false;
    seenRef.current = false;
    tokenRef.current = null;

    if (token === null) return;

    const rawState = location.state as Record<string, unknown> | null;
    const viewIds = Array.isArray(rawState?.view)
      ? (rawState.view as string[])
      : [];

    if (viewIds.length > 0 && viewIds[viewIds.length - 1] === token) {
      navigate(-1);
    }
  }, [open, id, location.state, navigate]);

  // Capture focus and scroll position once per open cycle, before the host
  // content becomes hidden.
  useLayoutEffect(() => {
    if (!open || openCycleRef.current) return;

    openCycleRef.current = true;
    savedFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    savedScrollYRef.current = window.scrollY;
  }, [open]);

  // Focus the first field (or the heading) once the section is visible.
  useEffect(() => {
    if (!open || !isTop || focusedRef.current) return;

    focusedRef.current = true;
    window.scrollTo(0, 0);

    const section = sectionRef.current;
    if (!section) return;

    if (autoFocus) {
      const fields = section.querySelectorAll<
        HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
      >("input, select, textarea");
      const firstEnabled = Array.from(fields).find(
        (field) => !field.disabled && !(field as HTMLInputElement).readOnly,
      );
      if (firstEnabled) {
        firstEnabled.focus();
        return;
      }
    }

    headingRef.current?.focus();
  }, [open, isTop, autoFocus]);

  // Reset per-open-cycle refs when the view closes.
  useEffect(() => {
    if (open) return;
    openCycleRef.current = false;
    focusedRef.current = false;
  }, [open]);

  // Restore focus and scroll position on close or unmount while open.
  useEffect(() => {
    if (open) return;

    const savedFocus = savedFocusRef.current;
    const savedScrollY = savedScrollYRef.current;

    if (savedFocus === null && savedScrollY === 0) return;

    window.setTimeout(() => {
      window.scrollTo(0, savedScrollY);
      if (savedFocus?.isConnected) {
        savedFocus.focus();
      }
    }, 0);

    savedFocusRef.current = null;
    savedScrollYRef.current = 0;
  }, [open]);

  // Restore on unmount while open.
  useEffect(() => {
    return () => {
      const savedFocus = savedFocusRef.current;
      const savedScrollY = savedScrollYRef.current;

      if (!openCycleRef.current) return;

      window.setTimeout(() => {
        window.scrollTo(0, savedScrollY);
        if (savedFocus?.isConnected) {
          savedFocus.focus();
        }
      }, 0);
    };
  }, []);

  // Close on Escape while this is the top view.
  useEffect(() => {
    if (!open || !isTop) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        onCloseRef.current();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, isTop]);

  if (!open || topHost === null) return null;

  return createPortal(
    <section
      ref={sectionRef}
      aria-labelledby={titleId}
      hidden={!isTop}
      className="space-y-5"
    >
      <div className="rounded-card border border-line-accent bg-surface p-5 sm:p-8">
        <div className="flex items-center gap-4">
          <button
            type="button"
            aria-label={t.common.back}
            onClick={() => onCloseRef.current()}
            className="inline-flex min-h-tap min-w-tap shrink-0 items-center justify-center rounded-xl border border-line bg-surface text-ink-2 hover:bg-subtle hover:text-accent"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden />
          </button>
          <h1
            ref={headingRef}
            id={titleId}
            tabIndex={-1}
            className="min-w-0 break-words text-2xl font-bold tracking-tight text-ink focus:outline-none sm:text-3xl"
          >
            {title}
          </h1>
        </div>
      </div>
      <div className="text-ink-3">{children}</div>
      {footer ? (
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          {footer}
        </div>
      ) : null}
    </section>,
    topHost.slot,
  );
}
