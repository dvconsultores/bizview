import { useEffect, useState } from "react";

/** How often a visible tab asks whether the deployed build changed (feature 025). */
export const VERSION_POLL_MS = 60_000;

const SCRIPT_TAG = /<script\b[^>]*>/gi;

/**
 * The entry asset of the bundle this page is running. Vite writes one module script into
 * `index.html` with the build hash in its name, so the file name changes with every build.
 */
export function loadedEntry(doc: Document = document): string | null {
  const el = doc.querySelector<HTMLScriptElement>('script[type="module"][src]');
  return el?.getAttribute("src") ?? null;
}

function entryFromHtml(html: string): string | null {
  for (const tag of html.match(SCRIPT_TAG) ?? []) {
    if (!/\btype="module"/i.test(tag)) continue;
    const src = tag.match(/\bsrc="([^"]+)"/i);
    if (src) return src[1];
  }
  return null;
}

/** The entry asset the server would serve now, read without touching any cache. */
export async function deployedEntry(
  base: string = import.meta.env.BASE_URL,
  fetchFn: typeof fetch = fetch,
): Promise<string | null> {
  const res = await fetchFn(`${base}index.html`, { cache: "no-store" });
  if (!res.ok) return null;
  return entryFromHtml(await res.text());
}

export interface VersionWatchOptions {
  /** The entry the page is running; a null value makes the watch inert (no entry script). */
  current: string | null;
  /** Reads the entry the server serves now. */
  fetchDeployed?: () => Promise<string | null>;
  onNewVersion: () => void;
  intervalMs?: number;
  doc?: Document;
}

/**
 * Watches the deployed entry document for a new build (feature 025): "a new version available"
 * means the bundle served now is not the one this tab is running. Polls only while the tab is
 * visible, checks at once when the tab comes back (a wall dashboard is the case that matters),
 * and stays silent when the server cannot be reached. Returns the stop function.
 */
export function startVersionWatch(options: VersionWatchOptions): () => void {
  const doc = options.doc ?? document;
  const fetchDeployed = options.fetchDeployed ?? (() => deployedEntry());
  const intervalMs = options.intervalMs ?? VERSION_POLL_MS;

  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let inFlight = false;
  let found = false;

  const schedule = (delay: number) => {
    if (stopped || found) return;
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      void tick();
    }, delay);
  };

  const tick = async () => {
    if (stopped || inFlight || found) return;
    if (doc.visibilityState === "hidden") return;
    inFlight = true;
    try {
      const entry = await fetchDeployed();
      if (stopped) return;
      if (entry !== null && options.current !== null && entry !== options.current) {
        found = true;
        options.onNewVersion();
        return;
      }
      schedule(intervalMs);
    } catch {
      // A failure is not news: try again next period.
      schedule(intervalMs);
    } finally {
      inFlight = false;
    }
  };

  const onVisibilityChange = () => {
    if (stopped || doc.visibilityState === "hidden") return;
    if (found) return;
    void tick();
  };

  if (options.current !== null) {
    doc.addEventListener("visibilitychange", onVisibilityChange);
    schedule(intervalMs);
  }

  return () => {
    stopped = true;
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    doc.removeEventListener("visibilitychange", onVisibilityChange);
  };
}

/** True once the installed bundle is not the one this tab is running. */
export function useNewVersion(): boolean {
  const [stale, setStale] = useState(false);

  useEffect(() => {
    if (stale) return;
    return startVersionWatch({ current: loadedEntry(), onNewVersion: () => setStale(true) });
  }, [stale]);

  return stale;
}

/** Takes the tab onto the deployed build. */
export function reloadApp(): void {
  window.location.reload();
}
