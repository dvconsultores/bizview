import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyTheme, isPreference, readCachedPreference, resolveTheme, STORAGE_KEY, systemPrefersDark,
  writeCachedPreference, type ThemePreference,
} from "../../src/theme/resolve";

const INIT_SCRIPT = readFileSync(join(process.cwd(), "public/theme-init.js"), "utf8");

function mockMatchMedia(dark: boolean | "missing") {
  if (dark === "missing") {
    // @ts-expect-error: simulate a browser without matchMedia
    window.matchMedia = undefined;
    return;
  }
  window.matchMedia = ((q: string) => ({
    matches: dark && q.includes("dark"), media: q, addEventListener() {}, removeEventListener() {},
  })) as unknown as typeof window.matchMedia;
}

function runInitScript() {
  new Function(INIT_SCRIPT)();
  return document.documentElement.dataset.theme;
}

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.head.innerHTML = '<meta name="theme-color" content="#3a7393">';
});
afterEach(() => vi.restoreAllMocks());

describe("theme resolution (feature 006)", () => {
  const cases: [ThemePreference, boolean, "light" | "dark"][] = [
    ["system", false, "light"], ["system", true, "dark"],
    ["light", false, "light"], ["light", true, "light"],
    ["dark", false, "dark"], ["dark", true, "dark"],
  ];

  it.each(cases)("%s with device dark=%s → %s", (pref, dark, expected) => {
    expect(resolveTheme(pref, dark)).toBe(expected);
  });

  it.each(cases)("theme-init.js agrees: %s with device dark=%s → %s", (pref, dark, expected) => {
    localStorage.setItem(STORAGE_KEY, pref);
    mockMatchMedia(dark);
    expect(runInitScript()).toBe(expected);
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute("content"))
      .toBe(expected === "dark" ? "#172b37" : "#3a7393");
  });

  it("treats an unknown cached value as system", () => {
    localStorage.setItem(STORAGE_KEY, "sepia");
    expect(readCachedPreference()).toBe("system");
    mockMatchMedia(true);
    expect(runInitScript()).toBe("dark");
  });

  it("falls back when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(readCachedPreference()).toBe("system");
    expect(() => writeCachedPreference("dark")).not.toThrow();
    mockMatchMedia(false);
    expect(runInitScript()).toBe("light");
  });

  it("uses light when the browser cannot report an appearance", () => {
    mockMatchMedia("missing");
    expect(systemPrefersDark()).toBe(false);
    expect(runInitScript()).toBe("light");
  });

  it("applies the resolved theme to the document", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute("content")).toBe("#172b37");
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("validates preferences", () => {
    expect(["system", "light", "dark"].every(isPreference)).toBe(true);
    expect(isPreference("sepia")).toBe(false);
    expect(isPreference(null)).toBe(false);
  });
});

describe("ThemeSwitcher", () => {
  const setPreference = vi.fn(async () => undefined);
  let preference: ThemePreference = "system";

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    setPreference.mockClear();
    preference = "system";
    vi.doMock("../../src/theme/ThemeContext", () => ({
      useTheme: () => ({ preference, resolved: "light", setPreference }),
    }));
  });

  async function render(inMenu = false) {
    const { ThemeSwitcher } = await import("../../src/components/ThemeSwitcher");
    const host = document.createElement("div");
    document.body.append(host);
    await act(async () => createRoot(host).render(createElement(ThemeSwitcher, { inMenu })));
    return host;
  }

  it("is a radio group with the current choice checked and roving focus", async () => {
    preference = "light";
    const host = await render();
    expect(host.querySelector('[role="radiogroup"]')?.getAttribute("aria-label")).toBe("Tema");
    const radios = [...host.querySelectorAll<HTMLButtonElement>('[role="radio"]')];
    expect(radios.map((r) => r.textContent)).toEqual(["Sistema", "Claro", "Oscuro"]);
    expect(radios.map((r) => r.getAttribute("aria-checked"))).toEqual(["false", "true", "false"]);
    expect(radios.map((r) => r.tabIndex)).toEqual([-1, 0, -1]);
  });

  it("arrow keys move focus and select, wrapping around", async () => {
    preference = "dark";
    const host = await render();
    const radios = [...host.querySelectorAll<HTMLButtonElement>('[role="radio"]')];
    await act(async () => { radios[2].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(setPreference).toHaveBeenLastCalledWith("system");
    expect(document.activeElement).toBe(radios[0]);
    await act(async () => { radios[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true })); });
    expect(setPreference).toHaveBeenLastCalledWith("dark");
  });

  it("inside the account menu uses menuitemradio items", async () => {
    const host = await render(true);
    expect(host.querySelector('[role="group"]')).not.toBeNull();
    const items = host.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]');
    expect(items).toHaveLength(3);
    await act(async () => { items[2].click(); });
    expect(setPreference).toHaveBeenCalledWith("dark");
  });
});
