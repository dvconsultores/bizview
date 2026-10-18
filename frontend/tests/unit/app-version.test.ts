/** Feature 025 US2: "a new version is available" reads the deployed entry document, so a
 * development server (whose entry never changes) never triggers it, and a failure is silent. */
import { describe, expect, it, vi, afterEach } from "vitest";

import { deployedEntry, loadedEntry, startVersionWatch, VERSION_POLL_MS } from "../../src/lib/appVersion";

const HTML = (entry: string) =>
  `<!doctype html><html><head><script type="module" crossorigin src="${entry}"></script></head><body></body></html>`;

function fakeDoc(visibility: DocumentVisibilityState = "visible") {
  const listeners = new Map<string, () => void>();
  return {
    doc: {
      get visibilityState() { return visibility; },
      addEventListener: (type: string, fn: () => void) => listeners.set(type, fn),
      removeEventListener: (type: string) => listeners.delete(type),
    } as unknown as Document,
    setVisibility(next: DocumentVisibilityState) { visibility = next; },
    fire: (type: string) => listeners.get(type)?.(),
    listeners,
  };
}

afterEach(() => vi.useRealTimers());

describe("the entry asset of the running bundle", () => {
  it("is the module script of the document", () => {
    const doc = new DOMParser().parseFromString(HTML("/assets/index-new.js"), "text/html");
    expect(loadedEntry(doc)).toBe("/assets/index-new.js");
  });

  it("is read from the deployed index.html without touching any cache", async () => {
    const fetchFn = vi.fn(async () => new Response(HTML("/assets/index-deployed.js")));
    await expect(deployedEntry("/", fetchFn as unknown as typeof fetch)).resolves.toBe("/assets/index-deployed.js");
    expect(fetchFn).toHaveBeenCalledWith("/index.html", { cache: "no-store" });
  });

  it("is null when the document cannot be read or has no entry script", async () => {
    await expect(deployedEntry("/", (async () => new Response("<html></html>")) as unknown as typeof fetch)).resolves.toBeNull();
    await expect(deployedEntry("/", (async () => new Response("gone", { status: 404 })) as unknown as typeof fetch)).resolves.toBeNull();
    expect(loadedEntry(new DOMParser().parseFromString("<html></html>", "text/html"))).toBeNull();
  });
});

describe("watching for a new build", () => {
  it("says nothing while the deployed entry is the one running", async () => {
    vi.useFakeTimers();
    const { doc } = fakeDoc();
    const onNewVersion = vi.fn();
    const stop = startVersionWatch({
      current: "/assets/index-old.js",
      fetchDeployed: async () => "/assets/index-old.js",
      onNewVersion,
      doc,
    });
    await vi.advanceTimersByTimeAsync(VERSION_POLL_MS * 3);
    expect(onNewVersion).not.toHaveBeenCalled();
    stop();
  });

  it("tells the page once when the deployed entry changed", async () => {
    vi.useFakeTimers();
    const { doc } = fakeDoc();
    const onNewVersion = vi.fn();
    const stop = startVersionWatch({
      current: "/assets/index-old.js",
      fetchDeployed: async () => "/assets/index-new.js",
      onNewVersion,
      doc,
    });
    await vi.advanceTimersByTimeAsync(VERSION_POLL_MS * 3);
    expect(onNewVersion).toHaveBeenCalledTimes(1);
    stop();
  });

  it("does not ask while the tab is hidden and checks at once when it comes back", async () => {
    vi.useFakeTimers();
    const view = fakeDoc("hidden");
    const fetchDeployed = vi.fn(async () => "/assets/index-old.js");
    const stop = startVersionWatch({ current: "/assets/index-old.js", fetchDeployed, onNewVersion: vi.fn(), doc: view.doc });
    await vi.advanceTimersByTimeAsync(VERSION_POLL_MS * 2);
    expect(fetchDeployed).not.toHaveBeenCalled();
    view.setVisibility("visible");
    view.fire("visibilitychange");
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchDeployed).toHaveBeenCalledTimes(1);
    stop();
    expect(view.listeners.size).toBe(0);
  });

  it("is silent when the server cannot be reached, and tries again", async () => {
    vi.useFakeTimers();
    const { doc } = fakeDoc();
    const fetchDeployed = vi.fn(async () => { throw new TypeError("offline"); });
    const onNewVersion = vi.fn();
    const stop = startVersionWatch({ current: "/assets/index-old.js", fetchDeployed, onNewVersion, doc });
    await vi.advanceTimersByTimeAsync(VERSION_POLL_MS * 2);
    expect(onNewVersion).not.toHaveBeenCalled();
    expect(fetchDeployed.mock.calls.length).toBeGreaterThanOrEqual(2);
    stop();
  });

  it("is inert when the page has no entry script", async () => {
    vi.useFakeTimers();
    const { doc } = fakeDoc();
    const fetchDeployed = vi.fn(async () => "/assets/index-new.js");
    const stop = startVersionWatch({ current: null, fetchDeployed, onNewVersion: vi.fn(), doc });
    await vi.advanceTimersByTimeAsync(VERSION_POLL_MS * 2);
    expect(fetchDeployed).not.toHaveBeenCalled();
    stop();
  });
});
