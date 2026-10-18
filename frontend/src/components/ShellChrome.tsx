import { createContext, useContext, useLayoutEffect } from "react";

export interface ShellChrome {
  /** True while a page asked the chrome (sidebar, top bar, tab bar, footer) to step aside. */
  hidden: boolean;
  /** False while the page asks for a kiosk-like mode where the chat has no place (the report's TV
   * mode). The project's full screen keeps it true: there the chat is the point (feature 025). */
  chat: boolean;
  setHidden: (state: { hidden: boolean; chat: boolean }) => void;
}

export const ShellChromeContext = createContext<ShellChrome>({
  hidden: false,
  chat: true,
  setHidden: () => undefined,
});

/**
 * Pages call this to hide the app chrome (sidebar, top bar, bottom tab bar, footer)
 * while `hidden` is true; restored on unmount or when false.
 * `keepChat` is false for modes meant to be looked at rather than worked in (TV mode).
 * useLayoutEffect runs before paint so the chrome never flashes on first render.
 */
export function useHideShellChrome(hidden: boolean, keepChat: boolean = true): void {
  const { setHidden } = useContext(ShellChromeContext);

  useLayoutEffect(() => {
    if (!hidden) return;
    setHidden({ hidden: true, chat: keepChat });
    return () => setHidden({ hidden: false, chat: keepChat });
  }, [hidden, keepChat, setHidden]);
}

/** The chrome state, for the parts of the shell that adapt to it (feature 025: the chat panel). */
export function useShellChrome(): ShellChrome {
  return useContext(ShellChromeContext);
}
