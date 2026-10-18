import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LocaleState } from "../../src/i18n";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type MockUser = { id: number; locale?: "es" | "en" | null };

let currentUser: MockUser | null = null;
const setUser = vi.fn((u: MockUser | null) => {
  currentUser = u;
});
const toast = vi.fn();
const api = { patch: vi.fn() };
let defaultLocale: "es" | "en" | undefined;

vi.doMock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: currentUser, setUser }),
}));
vi.doMock("../../src/components/Toast", () => ({
  useToast: () => toast,
}));
vi.doMock("../../src/api/client", () => ({
  api,
}));
vi.doMock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ default_locale: defaultLocale }),
}));

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setLanguages(list: string[]) {
  Object.defineProperty(navigator, "languages", {
    value: [...list],
    configurable: true,
  });
}

let state: LocaleState | null = null;
let probeT: unknown = null;
let root: Root | null = null;
let host: HTMLDivElement | null = null;

async function renderProvider() {
  const mod = await import("../../src/i18n");
  function Probe() {
    state = mod.useLocale();
    probeT = mod.useT();
    return null;
  }
  if (!root) {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  }
  await act(async () => {
    root!.render(createElement(mod.LocaleProvider, null, createElement(Probe)));
  });
  return mod;
}

async function unmountProvider() {
  if (!root) return;
  await act(async () => {
    root!.unmount();
  });
  host?.remove();
  root = null;
  host = null;
}

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  setUser.mockImplementation((u: MockUser | null) => {
    currentUser = u;
  });
  api.patch.mockReset();
  localStorage.clear();
  document.documentElement.lang = "es";
  setLanguages(["fr-FR"]);
  currentUser = null;
  defaultLocale = undefined;
  state = null;
  probeT = null;
});

afterEach(async () => {
  await unmountProvider();
});

describe("LocaleProvider", () => {
  it("uses the cached device locale when no user is signed in", async () => {
    localStorage.setItem("bizview.locale", "en");
    const mod = await renderProvider();
    expect(state!.locale).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    const enCatalogue = (await import("../../src/i18n/en")).en;
    expect(probeT).toBe(enCatalogue);
    expect(mod.t).toBe(enCatalogue);
    expect(mod.currentIntlTag()).toBe("en-US");
    expect(mod.currentLocale()).toBe("en");
    expect(state!.intlTag).toBe("en-US");
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("falls back to browser languages, then default, then es", async () => {
    setLanguages(["en-GB", "es"]);
    let mod = await renderProvider();
    expect(state!.locale).toBe("en");

    await unmountProvider();
    setLanguages(["fr"]);
    defaultLocale = "en";
    mod = await renderProvider();
    expect(state!.locale).toBe("en");

    await unmountProvider();
    defaultLocale = undefined;
    mod = await renderProvider();
    expect(state!.locale).toBe("es");
    const esCatalogue = (await import("../../src/i18n/es")).es;
    expect(mod.t).toBe(esCatalogue);
  });

  it("prefers the account locale over the device cache", async () => {
    localStorage.setItem("bizview.locale", "en");
    currentUser = { id: 1, locale: "es" };
    await renderProvider();
    expect(state!.locale).toBe("es");
    expect(document.documentElement.lang).toBe("es");
    expect(localStorage.getItem("bizview.locale")).toBe("es");
  });

  it("saves a device locale once to an account whose locale is still null", async () => {
    localStorage.setItem("bizview.locale", "en");
    currentUser = { id: 1, locale: null };
    api.patch.mockResolvedValue({ theme: "system", locale: "en" });
    await renderProvider();
    await act(async () => {}); // flush the one-time sync
    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(api.patch).toHaveBeenCalledWith("/api/me/preferences", { locale: "en" });
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({ locale: "en" }));

    // Force the same situation again; the ref guard must block a second call.
    currentUser = { id: 1, locale: null };
    await renderProvider();
    expect(api.patch).toHaveBeenCalledTimes(1);
  });

  it("does not sync when there is no device cache or the account has a locale", async () => {
    currentUser = { id: 1, locale: null };
    await renderProvider();
    expect(api.patch).not.toHaveBeenCalled();

    await unmountProvider();
    localStorage.setItem("bizview.locale", "en");
    currentUser = { id: 2 };
    await renderProvider();
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("applies only the latest preference when saves resolve out of order", async () => {
    currentUser = { id: 1, locale: "es" };
    const d1 = deferred<{ locale: "es" | "en" | null }>();
    const d2 = deferred<{ locale: "es" | "en" | null }>();
    api.patch.mockReturnValueOnce(d1.promise).mockReturnValueOnce(d2.promise);
    await renderProvider();

    let p1!: Promise<void>;
    let p2!: Promise<void>;
    await act(async () => {
      p1 = state!.setPreference("en");
      p2 = state!.setPreference("es");
    });

    await act(async () => {
      d2.resolve({ locale: "es" });
      d1.resolve({ locale: "en" });
      await p1;
      await p2;
    });

    expect(api.patch).toHaveBeenNthCalledWith(1, "/api/me/preferences", { locale: "en" });
    expect(api.patch).toHaveBeenNthCalledWith(2, "/api/me/preferences", { locale: "es" });
    expect(setUser).toHaveBeenCalledTimes(1);
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({ locale: "es" }));
    expect(document.documentElement.lang).toBe("es");
    expect(toast).not.toHaveBeenCalled();
  });

  it("keeps the applied locale and warns when the latest save fails", async () => {
    currentUser = { id: 1, locale: "es" };
    const d1 = deferred<{ locale: "es" | "en" | null }>();
    api.patch.mockReturnValueOnce(d1.promise);
    await renderProvider();

    let p!: Promise<void>;
    await act(async () => {
      p = state!.setPreference("en");
    });
    await act(async () => {
      d1.reject(new Error("network"));
      await p;
    });

    const enCatalogue = (await import("../../src/i18n/en")).en;
    expect(toast).toHaveBeenCalledWith(enCatalogue.language.saveFailed, "warning");
    expect(document.documentElement.lang).toBe("en");
    expect(localStorage.getItem("bizview.locale")).toBe("en");
    expect(setUser).not.toHaveBeenCalled();
  });

  it("stays silent when a stale save fails", async () => {
    currentUser = { id: 1, locale: "es" };
    const d1 = deferred<{ locale: "es" | "en" | null }>();
    const d2 = deferred<{ locale: "es" | "en" | null }>();
    api.patch.mockReturnValueOnce(d1.promise).mockReturnValueOnce(d2.promise);
    await renderProvider();

    let p1!: Promise<void>;
    let p2!: Promise<void>;
    await act(async () => {
      p1 = state!.setPreference("en");
      p2 = state!.setPreference("es");
    });
    await act(async () => {
      d2.resolve({ locale: "es" });
      d1.reject(new Error("network"));
      await p1;
      await p2;
    });

    expect(toast).not.toHaveBeenCalled();
  });

  it("follows the browser when the device cache is cleared", async () => {
    localStorage.setItem("bizview.locale", "es");
    setLanguages(["en"]);
    await renderProvider();
    expect(state!.locale).toBe("es");

    await act(async () => {
      await state!.setPreference(null);
    });
    expect(localStorage.getItem("bizview.locale")).toBeNull();
    expect(state!.locale).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("falls back to the es catalogue outside the provider", async () => {
    const mod = await import("../../src/i18n");
    const esCatalogue = (await import("../../src/i18n/es")).es;
    let probe: unknown = null;
    function Probe() {
      probe = mod.useT();
      return null;
    }
    const freshHost = document.createElement("div");
    document.body.appendChild(freshHost);
    const freshRoot = createRoot(freshHost);
    await act(async () => {
      freshRoot.render(createElement(Probe));
    });
    expect(probe).toBe(esCatalogue);
    await act(async () => {
      freshRoot.unmount();
    });
    freshHost.remove();
  });
});
