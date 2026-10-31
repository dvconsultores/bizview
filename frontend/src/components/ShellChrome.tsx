import { createContext, useContext, useLayoutEffect } from "react";

export interface ShellChrome {
  /** True while a page asked the chrome (sidebar, top bar, tab bar, footer) to step aside. */
  hidden: boolean;
  setHidden: (state: { hidden: boolean }) => void;
}

export const ShellChromeContext = createContext<ShellChrome>({
  hidden: false,
  setHidden: () => undefined,
});

/**
 * Pages call this to hide the app chrome (sidebar, top bar, bottom tab bar, footer)
 * while `hidden` is true; restored on unmount or when false.
 * useLayoutEffect runs before paint so the chrome never flashes on first render.
 */
export function useHideShellChrome(hidden: boolean): void {
  const { setHidden } = useContext(ShellChromeContext);

  useLayoutEffect(() => {
    if (!hidden) return;
    setHidden({ hidden: true });
    return () => setHidden({ hidden: false });
  }, [hidden, setHidden]);
}

/** The chrome state, for the parts of the shell that adapt to it. */
export function useShellChrome(): ShellChrome {
  return useContext(ShellChromeContext);
}
