/** Polling without overlap (feature 007): the next request is scheduled only after the previous
 * one settles; stops on a final value, an error, a time limit, or stop(). */
export interface PollOptions<T> {
  fetch: () => Promise<T>;
  isFinal: (v: T) => boolean;
  onValue: (v: T) => void;
  onError: (e: unknown) => void;
  intervalMs?: number;
  maxMs?: number;
  onTimeout?: () => void;
}

export function startPolling<T>(o: PollOptions<T>): () => void {
  const interval = o.intervalMs ?? 2000;
  const max = o.maxMs ?? 300_000;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let timeoutTimer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;
  let inFlight = false;

  const schedule = () => {
    if (stopped) return;
    timer = setTimeout(tick, interval);
  };

  const tick = async () => {
    if (stopped || inFlight) return;
    inFlight = true;
    try {
      const value = await o.fetch();
      if (stopped) return;
      o.onValue(value);
      if (o.isFinal(value)) {
        stop();
        return;
      }
    } catch (e) {
      if (stopped) return;
      o.onError(e);
      stop();
      return;
    } finally {
      inFlight = false;
    }
    schedule();
  };

  const stop = () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    if (timeoutTimer) clearTimeout(timeoutTimer);
  };

  timeoutTimer = setTimeout(() => {
    if (!stopped) {
      o.onTimeout?.();
      stop();
    }
  }, max);

  schedule();
  return stop;
}
