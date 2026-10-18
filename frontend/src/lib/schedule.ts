import { t } from "../i18n/live";

export type PresetId = "every15" | "every30" | "hourly" | "daily" | "custom";

export const PRESET_CRONS = {
  every15: "*/15 * * * *",
  every30: "*/30 * * * *",
  hourly: "0 * * * *",
} as const;

const NUMERIC_RE = /^\d+$/;

export function normalizeCron(expr: string): string {
  return expr.trim().split(/\s+/).join(" ");
}

/** Mirrors backend app.engine.schedule.describe: Spanish words for preset-like expressions. */
export function describeCron(expr: string): string | null {
  const norm = normalizeCron(expr);
  const fields = norm.split(" ");
  if (fields.length !== 5) return null;
  if (fields[2] !== "*" || fields[3] !== "*" || fields[4] !== "*") return null;

  const minute = fields[0];
  const hour = fields[1];

  if (minute.startsWith("*/") && hour === "*") {
    const nStr = minute.slice(2);
    if (!NUMERIC_RE.test(nStr)) return null;
    const n = Number(nStr);
    if (n >= 1 && n <= 59 && 60 % n === 0) {
      return n === 1 ? t.integrations.words.everyMinute : t.integrations.words.everyMinutes(n);
    }
  }

  if (minute === "0" && hour === "*") {
    return t.integrations.words.hourly;
  }

  if (minute === "0" && hour.startsWith("*/")) {
    const nStr = hour.slice(2);
    if (!NUMERIC_RE.test(nStr)) return null;
    const n = Number(nStr);
    if (n >= 2 && n <= 23 && 24 % n === 0) {
      return t.integrations.words.everyHours(n);
    }
  }

  if (NUMERIC_RE.test(minute) && NUMERIC_RE.test(hour)) {
    const m = Number(minute);
    const h = Number(hour);
    if (m >= 0 && m <= 59 && h >= 0 && h <= 23) {
      const hh = String(h).padStart(2, "0");
      const mm = String(m).padStart(2, "0");
      return t.integrations.words.dailyAt(`${hh}:${mm}`);
    }
  }

  return null;
}

export function presetFromCron(expr: string): { preset: PresetId; time: string; custom: string } {
  const norm = normalizeCron(expr);

  if (norm === PRESET_CRONS.every15) return { preset: "every15", time: "03:00", custom: "" };
  if (norm === PRESET_CRONS.every30) return { preset: "every30", time: "03:00", custom: "" };
  if (norm === PRESET_CRONS.hourly) return { preset: "hourly", time: "03:00", custom: "" };

  const fields = norm.split(" ");
  if (
    fields.length === 5 &&
    fields[2] === "*" &&
    fields[3] === "*" &&
    fields[4] === "*" &&
    NUMERIC_RE.test(fields[0]) &&
    NUMERIC_RE.test(fields[1])
  ) {
    const m = Number(fields[0]);
    const h = Number(fields[1]);
    if (m >= 0 && m <= 59 && h >= 0 && h <= 23) {
      const hh = String(h).padStart(2, "0");
      const mm = String(m).padStart(2, "0");
      return { preset: "daily", time: `${hh}:${mm}`, custom: "" };
    }
  }

  return { preset: "custom", time: "03:00", custom: norm };
}

export function cronFromPreset(preset: PresetId, time: string, custom: string): string {
  if (preset === "every15") return PRESET_CRONS.every15;
  if (preset === "every30") return PRESET_CRONS.every30;
  if (preset === "hourly") return PRESET_CRONS.hourly;

  if (preset === "daily") {
    const match = /^(\d{1,2}):(\d{2})$/.exec(time);
    if (!match) return normalizeCron(custom);
    const h = Number(match[1]);
    const m = Number(match[2]);
    if (h < 0 || h > 23 || m < 0 || m > 59) return normalizeCron(custom);
    return `${m} ${h} * * *`;
  }

  return normalizeCron(custom);
}

export function frequencyWords(expr: string, words?: string | null): string {
  return words ?? describeCron(expr) ?? normalizeCron(expr);
}

/** Mirrors backend in_window: start==end means always; start<end: start<=t<end; overnight: t>=start || t<end. Times "HH:MM". */
export function inWindow(hhmm: string, window: { start: string; end: string } | null): boolean {
  if (!window) return true;
  const at = parseMinutes(hhmm);
  if (at === null) return true;
  const start = parseMinutes(window.start);
  const end = parseMinutes(window.end);
  if (start === null || end === null) return true;

  if (start === end) return true;
  if (start < end) return at >= start && at < end;
  return at >= start || at < end;
}

/** Returns the "HH:MM" of the first daily full-rebuild cron ("m h * * *", numeric m/h) whose time falls outside the window, or null (no window, no daily cron, or all inside). Non-daily crons are ignored. */
export function fullRebuildOutsideWindow(
  crons: string[],
  window: { start: string; end: string } | null,
): string | null {
  if (!window) return null;

  for (const cron of crons) {
    const norm = normalizeCron(cron);
    const fields = norm.split(" ");
    if (fields.length !== 5) continue;
    if (fields[2] !== "*" || fields[3] !== "*" || fields[4] !== "*") continue;
    if (!NUMERIC_RE.test(fields[0]) || !NUMERIC_RE.test(fields[1])) continue;

    const m = Number(fields[0]);
    const h = Number(fields[1]);
    if (m < 0 || m > 59 || h < 0 || h > 23) continue;

    const hh = String(h).padStart(2, "0");
    const mm = String(m).padStart(2, "0");
    const time = `${hh}:${mm}`;

    if (!inWindow(time, window)) return time;
  }

  return null;
}

function parseMinutes(hhmm: string): number | null {
  const trimmed = hhmm.trim();
  if (!/^\d{1,2}:\d{2}(:\d{2})?$/.test(trimmed)) return null;

  const parts = trimmed.split(":");
  const h = Number(parts[0]);
  const m = Number(parts[1]);
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;

  return h * 60 + m;
}
