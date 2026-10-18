import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

let currentUser: { id: number; theme: string } = { id: 1, theme: "system" };
const setUser = vi.fn((u: { id: number; theme: string }) => {
  currentUser = u;
});
const toast = vi.fn();
const api = { patch: vi.fn() };

vi.doMock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, setUser }),
}));
vi.doMock("../../src/components/Toast", () => ({
  useToast: () => toast,
}));
vi.doMock("../../src/api/client", () => ({ api }));

let state: { setPreference: (p: "system" | "light" | "dark") => Promise<void> } | null = null;
let root: Root | null = null;
let host: HTMLDivElement | null = null;

async function renderProvider() {
  const { ThemeProvider, useTheme } = await import("../../src/theme/ThemeContext");
  function Probe() {
    state = useTheme();
    return null;
  }
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(createElement(ThemeProvider, null, createElement(Probe)));
  });
}

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  currentUser = { id: 1, theme: "system" };
  setUser.mockImplementation((u: { id: number; theme: string }) => {
    currentUser = u;
  });
  localStorage.clear();
  document.documentElement.dataset.theme = "system";
  window.matchMedia = (() => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  })) as unknown as typeof window.matchMedia;
});

afterEach(async () => {
  if (root) {
    await act(async () => {
      root!.unmount();
    });
    root = null;
  }
  if (host) {
    host.remove();
    host = null;
  }
});

describe("ThemeProvider race handling", () => {
  it("only the latest choice updates the account when responses arrive out of order", async () => {
    const d1 = deferred<{ theme: string }>();
    const d2 = deferred<{ theme: string }>();
    api.patch
      .mockReturnValueOnce(d1.promise)
      .mockReturnValueOnce(d2.promise);

    await renderProvider();
    expect(state).not.toBeNull();

    let p1!: Promise<void>;
    let p2!: Promise<void>;
    await act(async () => {
      p1 = state!.setPreference("dark");
      p2 = state!.setPreference("light");
    });

    // Resolve the second (latest) request first, then the first.
    d2.resolve({ theme: "light" });
    d1.resolve({ theme: "dark" });

    await act(async () => {
      await Promise.all([p1, p2]);
    });

    expect(api.patch).toHaveBeenNthCalledWith(1, "/api/me/preferences", { theme: "dark" });
    expect(api.patch).toHaveBeenNthCalledWith(2, "/api/me/preferences", { theme: "light" });
    expect(setUser).toHaveBeenCalledTimes(1);
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({ theme: "light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(toast).not.toHaveBeenCalled();
  });

  it("a stale failure does not warn", async () => {
    const d1 = deferred<{ theme: string }>();
    const d2 = deferred<{ theme: string }>();
    api.patch
      .mockReturnValueOnce(d1.promise)
      .mockReturnValueOnce(d2.promise);

    await renderProvider();
    expect(state).not.toBeNull();

    let p1!: Promise<void>;
    let p2!: Promise<void>;
    await act(async () => {
      p1 = state!.setPreference("dark");
      p2 = state!.setPreference("light");
    });

    // Resolve the latest request first, then reject the stale one.
    d2.resolve({ theme: "light" });
    d1.reject(new Error("network"));

    await act(async () => {
      await Promise.all([p1.catch(() => {}), p2]);
    });

    expect(toast).not.toHaveBeenCalled();
  });

  it("the latest failure warns and keeps the applied theme", async () => {
    const d1 = deferred<{ theme: string }>();
    api.patch.mockReturnValueOnce(d1.promise);

    await renderProvider();
    expect(state).not.toBeNull();

    let p!: Promise<void>;
    await act(async () => {
      p = state!.setPreference("dark");
    });

    d1.reject(new Error("network"));

    await act(async () => {
      await p.catch(() => {});
    });

    const { t } = await import("../../src/i18n/es");
    expect(toast).toHaveBeenCalledWith(t.theme.saveFailed, "warning");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("choosing the account's current value after another choice still saves it", async () => {
    currentUser.theme = "system";
    const d1 = deferred<{ theme: string }>();
    const d2 = deferred<{ theme: string }>();
    api.patch
      .mockReturnValueOnce(d1.promise)
      .mockReturnValueOnce(d2.promise);

    await renderProvider();
    expect(state).not.toBeNull();

    let p1!: Promise<void>;
    let p2!: Promise<void>;
    await act(async () => {
      p1 = state!.setPreference("dark");
      p2 = state!.setPreference("system");
    });

    d1.resolve({ theme: "dark" });
    d2.resolve({ theme: "system" });

    await act(async () => {
      await Promise.all([p1, p2]);
    });

    expect(api.patch).toHaveBeenCalledTimes(2);
    expect(setUser).toHaveBeenCalledTimes(1);
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({ theme: "system" }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
