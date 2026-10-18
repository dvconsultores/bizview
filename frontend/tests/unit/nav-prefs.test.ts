/** Feature 025: the left menu's collapsed state is a device choice, remembered between visits. */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { readNavCollapsed, writeNavCollapsed } from "../../src/lib/navPrefs";

beforeEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("the left menu preference", () => {
  it("starts expanded", () => {
    expect(readNavCollapsed()).toBe(false);
  });

  it("remembers a collapse and a return to expanded", () => {
    writeNavCollapsed(true);
    expect(readNavCollapsed()).toBe(true);
    expect(window.localStorage.getItem("bizview.nav")).toBe("collapsed");

    writeNavCollapsed(false);
    expect(readNavCollapsed()).toBe(false);
    expect(window.localStorage.getItem("bizview.nav")).toBeNull();
  });

  it("ignores anything else stored under that key", () => {
    window.localStorage.setItem("bizview.nav", "sideways");
    expect(readNavCollapsed()).toBe(false);
  });

  it("stays expanded when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readNavCollapsed()).toBe(false);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => writeNavCollapsed(true)).not.toThrow();
  });
});
