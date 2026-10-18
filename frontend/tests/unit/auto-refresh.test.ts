import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { activate } from "../../src/i18n/live";
import {
  formatClock,
  readAutoRefreshMode,
  startAutoRefresh,
  writeAutoRefreshMode,
} from "../../src/lib/autoRefresh";
import { ApiError } from "../../src/api/client";

function setVisibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event("visibilitychange"));
}

function createDeferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("startAutoRefresh", () => {
  const stops: Array<() => void> = [];

  const start = (o: Parameters<typeof startAutoRefresh>[0]) => {
    const s = startAutoRefresh(o);
    stops.push(s);
    return s;
  };

  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility("visible");
  });

  afterEach(() => {
    for (const s of stops) s();
    stops.length = 0;
    vi.useRealTimers();
    vi.restoreAllMocks();
    setVisibility("visible");
  });

  it("data mode with unchanged version: fetchVersion called 180 times over 3 hours, onRefresh 0 times", async () => {
    const fetchVersion = vi.fn().mockResolvedValue("v1");
    const knownVersion = () => "v1";
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
    });

    // 3 hours = 180 * 60s
    for (let i = 0; i < 180; i++) {
      await vi.advanceTimersByTimeAsync(60_000);
    }

    expect(fetchVersion).toHaveBeenCalledTimes(180);
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("data mode: version change triggers exactly one refresh; later polls do not refresh again", async () => {
    let currentVersion = "v1";
    let fetchedVersion = "v1";
    const fetchVersion = vi.fn().mockImplementation(async () => fetchedVersion);
    const knownVersion = () => currentVersion;
    const onRefresh = vi.fn().mockImplementation(async () => {
      currentVersion = fetchedVersion;
    });

    const stop = start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
    });

    // First poll at 60s: unchanged
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);
    expect(onRefresh).not.toHaveBeenCalled();

    // Change the server version
    fetchedVersion = "v2";

    // Second poll at 120s: change detected
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(2);
    expect(onRefresh).toHaveBeenCalledTimes(1);
    // knownVersion was updated by onRefresh
    expect(currentVersion).toBe("v2");

    // Third poll at 180s: unchanged (both v2)
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(3);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    stop();
  });

  it("hidden: no fetchVersion while hidden for 10 minutes; on visible immediate check and refresh if changed", async () => {
    let fetchedVersion = "v1";
    let currentVersion = "v1";
    const fetchVersion = vi.fn().mockImplementation(async () => fetchedVersion);
    const knownVersion = () => currentVersion;
    const onRefresh = vi.fn().mockImplementation(async () => {
      currentVersion = fetchedVersion;
    });

    start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
    });

    // Poll at 60s (visible)
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);

    // Go hidden for 10 minutes
    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(600_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);

    // Change version while hidden
    fetchedVersion = "v2";

    // Become visible: immediate tick
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchVersion).toHaveBeenCalledTimes(2);
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(currentVersion).toBe("v2");
  });

  it('interval "5": onRefresh at 5 and 10 min, fetchVersion never called; hidden for 7 min then visible -> immediate refresh', async () => {
    const fetchVersion = vi.fn().mockResolvedValue("v1");
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const nowRef = { value: 0 };
    const now = () => nowRef.value;

    start({
      mode: "5",
      fetchVersion,
      knownVersion: () => "v1",
      onRefresh,
      now,
    });

    // First tick at 5 min
    nowRef.value += 5 * 60_000;
    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(fetchVersion).not.toHaveBeenCalled();

    // Second tick at 10 min
    nowRef.value += 5 * 60_000;
    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(onRefresh).toHaveBeenCalledTimes(2);
    expect(fetchVersion).not.toHaveBeenCalled();

    // Hidden for 7 minutes
    setVisibility("hidden");
    nowRef.value += 7 * 60_000;
    await vi.advanceTimersByTimeAsync(7 * 60_000);
    expect(onRefresh).toHaveBeenCalledTimes(2);

    // Become visible: elapsed >= P, immediate tick
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    await Promise.resolve();
    await Promise.resolve();

    expect(onRefresh).toHaveBeenCalledTimes(3);
    expect(fetchVersion).not.toHaveBeenCalled();
  });

  it("network error (ApiError status 0): onStatus offline once, retries at 5s then 10s; success -> ok", async () => {
    let shouldFail = true;
    const fetchVersion = vi.fn().mockImplementation(async () => {
      if (shouldFail) {
        throw new ApiError(0, "network", "No hay conexión");
      }
      return "v1";
    });
    const knownVersion = () => null;
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const onStatus = vi.fn();

    start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
      onStatus,
    });

    // First tick at 60s: network error
    await vi.advanceTimersByTimeAsync(60_000);
    expect(onStatus).toHaveBeenCalledTimes(1);
    expect(onStatus).toHaveBeenLastCalledWith("offline");

    // Retry at 5s: still failing (backoff now 10s)
    await vi.advanceTimersByTimeAsync(5_000);
    expect(fetchVersion).toHaveBeenCalledTimes(2);
    expect(onStatus).toHaveBeenCalledTimes(1); // still offline, no change

    // Retry at 10s: success
    shouldFail = false;
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetchVersion).toHaveBeenCalledTimes(3);
    expect(onStatus).toHaveBeenCalledTimes(2);
    expect(onStatus).toHaveBeenLastCalledWith("ok");
  });

  it("500 ApiError does not report offline and retries after normal period", async () => {
    let shouldFail = true;
    const fetchVersion = vi.fn().mockImplementation(async () => {
      if (shouldFail) {
        throw new ApiError(500, "server_error", "Error interno");
      }
      return "v1";
    });
    const knownVersion = () => null;
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const onStatus = vi.fn();

    start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
      onStatus,
    });

    // First tick at 60s: 500 error
    await vi.advanceTimersByTimeAsync(60_000);
    expect(onStatus).not.toHaveBeenCalled();

    // Next tick at 120s (normal period, not backoff)
    shouldFail = false;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(2);
    expect(onStatus).not.toHaveBeenCalled();
  });

  it("no overlap: slow onRefresh blocks further ticks until it settles", async () => {
    let resolveFirst!: () => void;
    let callCount = 0;
    const onRefresh = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return new Promise<void>((resolve) => {
          resolveFirst = resolve;
        });
      }
      return Promise.resolve();
    });

    start({
      mode: "1",
      fetchVersion: vi.fn().mockResolvedValue("v1"),
      knownVersion: () => "v1",
      onRefresh,
    });

    // First tick at 60s starts and is slow
    await vi.advanceTimersByTimeAsync(60_000);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    // Advance 2 more minutes: no new ticks because first is still in flight
    await vi.advanceTimersByTimeAsync(120_000);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    // Resolve the first call
    resolveFirst();
    await Promise.resolve();
    await Promise.resolve();

    // Next tick schedules after P from resolution
    await vi.advanceTimersByTimeAsync(60_000);
    expect(onRefresh).toHaveBeenCalledTimes(2);
  });

  it("stop() prevents further calls including in-flight result triggering onRefresh", async () => {
    const unresolved = createDeferred<string>();
    const fetchVersion = vi.fn().mockReturnValue(unresolved.promise);
    const knownVersion = () => null;
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const onStatus = vi.fn();

    const stop = start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
      onStatus,
    });

    // First tick at 60s starts the fetch
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);

    // Stop while fetch is in flight
    stop();

    // Resolve the fetch with a new version
    unresolved.resolve("v2");
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(onRefresh).not.toHaveBeenCalled();

    // Advance time: no further fetch calls either
    await vi.advanceTimersByTimeAsync(600_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);
    expect(onStatus).not.toHaveBeenCalled();
  });

  it("data mode: knownVersion null is treated as stale, refreshedTo prevents reload loop", async () => {
    const fetchVersion = vi.fn().mockResolvedValue("v1");
    const knownVersion = vi.fn().mockReturnValue(null);
    const onRefresh = vi.fn().mockResolvedValue(undefined);

    start({
      mode: "data",
      fetchVersion,
      knownVersion,
      onRefresh,
    });

    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(2);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("data mode: visible again 30 s after last check schedules the remaining time", async () => {
    const fetchVersion = vi.fn(async () => "v2");
    const onRefresh = vi.fn(async () => true);

    start({
      mode: "data",
      fetchVersion,
      knownVersion: () => "v1",
      onRefresh,
    });

    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchVersion).toHaveBeenCalledTimes(1);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(30_000);
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchVersion).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(29_999);
    expect(fetchVersion).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(fetchVersion).toHaveBeenCalledTimes(2);
  });

  it("data mode: onRefresh resolving false is retried for the same version", async () => {
    const fetchVersion = vi.fn(async () => "v2");
    const onRefresh = vi
      .fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true);

    start({
      mode: "data",
      fetchVersion,
      knownVersion: () => "v1",
      onRefresh,
    });

    await vi.advanceTimersByTimeAsync(60_000);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(onRefresh).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(onRefresh).toHaveBeenCalledTimes(2);
    expect(fetchVersion).toHaveBeenCalledTimes(3);
  });

  it("stop() removes the visibilitychange listener", () => {
    const addSpy = vi.spyOn(document, "addEventListener");
    const removeSpy = vi.spyOn(document, "removeEventListener");

    const stop = start({
      mode: "data",
      fetchVersion: async () => "v1",
      knownVersion: () => null,
      onRefresh: async () => true,
    });

    const addCalls = addSpy.mock.calls.filter(([type]) => type === "visibilitychange");
    expect(addCalls.length).toBe(1);
    const listener = addCalls[0][1];

    stop();

    const removeCalls = removeSpy.mock.calls.filter(([type]) => type === "visibilitychange");
    expect(removeCalls.length).toBe(1);
    expect(removeCalls[0][1]).toBe(listener);
  });
});

describe("readAutoRefreshMode / writeAutoRefreshMode", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round trip: write then read", () => {
    writeAutoRefreshMode("r1", "5");
    expect(readAutoRefreshMode("r1")).toBe("5");

    writeAutoRefreshMode("r1", "data");
    expect(readAutoRefreshMode("r1")).toBe("data");
  });

  it("invalid stored value -> off", () => {
    localStorage.setItem("bizview.autorefresh.r1", "invalid");
    expect(readAutoRefreshMode("r1")).toBe("off");
  });

  it('"off" removes the key', () => {
    writeAutoRefreshMode("r1", "15");
    expect(localStorage.getItem("bizview.autorefresh.r1")).toBe("15");

    writeAutoRefreshMode("r1", "off");
    expect(localStorage.getItem("bizview.autorefresh.r1")).toBeNull();
  });

  it("localStorage throwing: no throw, returns off", () => {
    const getItemSpy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });

    expect(readAutoRefreshMode("r1")).toBe("off");
    expect(() => writeAutoRefreshMode("r1", "5")).not.toThrow();

    getItemSpy.mockRestore();
    setItemSpy.mockRestore();
  });
});

describe("formatClock follows the active language", () => {
  it("switches between Spanish and English", () => {
    activate("en");
    try {
      expect(formatClock(new Date(2026, 0, 1, 14, 5))).toMatch(/^02:05\sPM$/);
      activate("es");
      expect(formatClock(new Date(2026, 0, 1, 14, 5))).toBe("14:05");
    } finally {
      activate("es");
    }
  });
});
