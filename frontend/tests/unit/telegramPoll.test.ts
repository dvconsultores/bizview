import { afterEach, describe, expect, it, vi } from "vitest";
import { startPolling } from "../../src/lib/telegramPoll";

afterEach(() => vi.useRealTimers());

describe("startPolling (feature 007)", () => {
  it("polls until a final value", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn()
      .mockResolvedValueOnce({ n: 1 })
      .mockResolvedValueOnce({ n: 2 })
      .mockResolvedValueOnce({ n: 3 });
    const onValue = vi.fn();
    const stop = startPolling<{ n: number }>({
      fetch,
      isFinal: (v) => v.n >= 2,
      onValue,
      onError: vi.fn(),
      intervalMs: 100,
    });
    await vi.advanceTimersByTimeAsync(100);
    await vi.advanceTimersByTimeAsync(100);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(onValue).toHaveBeenCalledTimes(2);
    expect(onValue).toHaveBeenLastCalledWith({ n: 2 });
    await vi.advanceTimersByTimeAsync(500);
    expect(fetch).toHaveBeenCalledTimes(2);
    stop();
  });

  it("does not overlap requests", async () => {
    vi.useFakeTimers();
    let resolve: (v: { n: number }) => void = () => {};
    const fetch = vi.fn(() => new Promise<{ n: number }>((r) => (resolve = r)));
    const stop = startPolling<{ n: number }>({
      fetch,
      isFinal: () => false,
      onValue: vi.fn(),
      onError: vi.fn(),
      intervalMs: 100,
    });
    await vi.advanceTimersByTimeAsync(100);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(300);
    expect(fetch).toHaveBeenCalledTimes(1);
    resolve({ n: 1 });
    await vi.advanceTimersByTimeAsync(100);
    expect(fetch).toHaveBeenCalledTimes(2);
    stop();
  });

  it("stops on error and calls onError once", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockRejectedValueOnce(new Error("boom"));
    const onError = vi.fn();
    startPolling({ fetch, isFinal: () => false, onValue: vi.fn(), onError, intervalMs: 100 });
    await vi.advanceTimersByTimeAsync(100);
    expect(onError).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(500);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("stops after maxMs and calls onTimeout", async () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    const fetch = vi.fn().mockResolvedValue({ n: 1 });
    startPolling({
      fetch,
      isFinal: () => false,
      onValue: vi.fn(),
      onError: vi.fn(),
      intervalMs: 100,
      maxMs: 250,
      onTimeout,
    });
    await vi.advanceTimersByTimeAsync(250);
    expect(onTimeout).toHaveBeenCalledTimes(1);
    const calls = fetch.mock.calls.length;
    await vi.advanceTimersByTimeAsync(500);
    expect(fetch.mock.calls.length).toBe(calls);
  });

  it("stop() prevents callbacks after a request resolves", async () => {
    vi.useFakeTimers();
    let resolve: (v: { n: number }) => void = () => {};
    const fetch = vi.fn(() => new Promise<{ n: number }>((r) => (resolve = r)));
    const onValue = vi.fn();
    const stop = startPolling<{ n: number }>({
      fetch,
      isFinal: () => false,
      onValue,
      onError: vi.fn(),
      intervalMs: 100,
    });
    await vi.advanceTimersByTimeAsync(100);
    stop();
    resolve({ n: 1 });
    await vi.advanceTimersByTimeAsync(0);
    expect(onValue).not.toHaveBeenCalled();
  });
});
