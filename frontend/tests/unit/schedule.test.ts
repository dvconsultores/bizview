import { describe, expect, it } from "vitest";
import {
  PRESET_CRONS,
  cronFromPreset,
  describeCron,
  frequencyWords,
  fullRebuildOutsideWindow,
  inWindow,
  normalizeCron,
  presetFromCron,
} from "../../src/lib/schedule";

describe("normalizeCron", () => {
  it("trims and collapses whitespace", () => {
    expect(normalizeCron("  */15   *  * * *  ")).toBe("*/15 * * * *");
    expect(normalizeCron("0\t 3\n* * *")).toBe("0 3 * * *");
  });
});

describe("describeCron", () => {
  it("describes */15", () => {
    expect(describeCron("*/15 * * * *")).toBe("Cada 15 minutos");
  });

  it("describes */30", () => {
    expect(describeCron("*/30 * * * *")).toBe("Cada 30 minutos");
  });

  it("describes */1 as Cada minuto", () => {
    expect(describeCron("*/1 * * * *")).toBe("Cada minuto");
  });

  it("describes hourly", () => {
    expect(describeCron("0 * * * *")).toBe("Cada hora");
  });

  it("describes every 2 hours", () => {
    expect(describeCron("0 */2 * * *")).toBe("Cada 2 horas");
  });

  it("describes daily at 03:00", () => {
    expect(describeCron("0 3 * * *")).toBe("Diaria a las 03:00");
  });

  it("describes daily at 22:05", () => {
    expect(describeCron("5 22 * * *")).toBe("Diaria a las 22:05");
  });

  it("accepts extra whitespace", () => {
    expect(describeCron("  0   3  * * *  ")).toBe("Diaria a las 03:00");
    expect(describeCron("*/15\t*\t*\t*\t*")).toBe("Cada 15 minutos");
  });

  it("returns null for non-describable expressions", () => {
    expect(describeCron("5 4 * * 1")).toBeNull();
    expect(describeCron("0 3 1 * *")).toBeNull();
    expect(describeCron("*/0 * * * *")).toBeNull();
    expect(describeCron("bad")).toBeNull();
    expect(describeCron("")).toBeNull();
    expect(describeCron("*/x * * * *")).toBeNull();
    expect(describeCron("60 3 * * *")).toBeNull();
  });
});

describe("presetFromCron", () => {
  it("detects every15", () => {
    expect(presetFromCron("*/15 * * * *")).toEqual({ preset: "every15", time: "03:00", custom: "" });
  });

  it("detects every30", () => {
    expect(presetFromCron("*/30 * * * *")).toEqual({ preset: "every30", time: "03:00", custom: "" });
  });

  it("detects hourly", () => {
    expect(presetFromCron("0 * * * *")).toEqual({ preset: "hourly", time: "03:00", custom: "" });
  });

  it("detects daily with zero-padded time", () => {
    expect(presetFromCron("0 3 * * *")).toEqual({ preset: "daily", time: "03:00", custom: "" });
  });

  it("detects daily with non-padded minute and hour", () => {
    expect(presetFromCron("5 22 * * *")).toEqual({ preset: "daily", time: "22:05", custom: "" });
  });

  it("detects daily with extra whitespace", () => {
    expect(presetFromCron("  0   7  * * *  ")).toEqual({ preset: "daily", time: "07:00", custom: "" });
  });

  it("falls back to custom with normalised expression", () => {
    expect(presetFromCron("5 4 * * 1")).toEqual({ preset: "custom", time: "03:00", custom: "5 4 * * 1" });
    expect(presetFromCron("  0 3  1 * * ")).toEqual({ preset: "custom", time: "03:00", custom: "0 3 1 * *" });
    expect(presetFromCron("bad")).toEqual({ preset: "custom", time: "03:00", custom: "bad" });
  });
});

describe("cronFromPreset", () => {
  it("maps every15", () => {
    expect(cronFromPreset("every15", "03:00", "")).toBe(PRESET_CRONS.every15);
  });

  it("maps every30", () => {
    expect(cronFromPreset("every30", "03:00", "")).toBe(PRESET_CRONS.every30);
  });

  it("maps hourly", () => {
    expect(cronFromPreset("hourly", "03:00", "")).toBe(PRESET_CRONS.hourly);
  });

  it("maps daily 03:00", () => {
    expect(cronFromPreset("daily", "03:00", "")).toBe("0 3 * * *");
  });

  it("maps daily 22:05", () => {
    expect(cronFromPreset("daily", "22:05", "")).toBe("5 22 * * *");
  });

  it("maps custom with normalisation", () => {
    expect(cronFromPreset("custom", "03:00", "  0 3  1 * * ")).toBe("0 3 1 * *");
  });
});

describe("round trips", () => {
  it("preset → cron → preset for every non-custom preset", () => {
    for (const p of ["every15", "every30", "hourly"] as const) {
      expect(presetFromCron(cronFromPreset(p, "03:00", "")).preset).toBe(p);
    }
    expect(presetFromCron(cronFromPreset("daily", "07:30", "")).preset).toBe("daily");
  });

  it("daily round trip preserves time", () => {
    const cron = cronFromPreset("daily", "07:30", "");
    expect(presetFromCron(cron)).toEqual({ preset: "daily", time: "07:30", custom: "" });
    expect(describeCron(cron)).toBe("Diaria a las 07:30");
  });
});

describe("frequencyWords", () => {
  it("prefers the given words", () => {
    expect(frequencyWords("*/15 * * * *", "Cada cuarto de hora")).toBe("Cada cuarto de hora");
    expect(frequencyWords("*/15 * * * *", null)).toBe("Cada 15 minutos");
  });

  it("falls back to describeCron", () => {
    expect(frequencyWords("0 3 * * *", null)).toBe("Diaria a las 03:00");
  });

  it("falls back to the normalised cron", () => {
    expect(frequencyWords("5 4 * * 1", null)).toBe("5 4 * * 1");
    expect(frequencyWords("  5   4  * * 1 ", null)).toBe("5 4 * * 1");
  });
});

describe("describeCron divisibility", () => {
  it("returns null for minute step that does not divide 60", () => {
    expect(describeCron("*/25 * * * *")).toBeNull();
    expect(describeCron("*/7 * * * *")).toBeNull();
  });

  it("returns null for hour step that does not divide 24", () => {
    expect(describeCron("0 */5 * * *")).toBeNull();
    expect(describeCron("0 */7 * * *")).toBeNull();
  });

  it("returns words for minute step that divides 60", () => {
    expect(describeCron("*/20 * * * *")).toBe("Cada 20 minutos");
  });

  it("returns words for hour step that divides 24", () => {
    expect(describeCron("0 */6 * * *")).toBe("Cada 6 horas");
    expect(describeCron("0 */12 * * *")).toBe("Cada 12 horas");
  });
});

describe("inWindow", () => {
  const standard = { start: "06:00", end: "22:00" };

  it("treats null window as always inside", () => {
    expect(inWindow("03:00", null)).toBe(true);
    expect(inWindow("12:00", null)).toBe(true);
  });

  it("handles start < end (inclusive start, exclusive end)", () => {
    expect(inWindow("05:59", standard)).toBe(false);
    expect(inWindow("06:00", standard)).toBe(true);
    expect(inWindow("12:00", standard)).toBe(true);
    expect(inWindow("21:59", standard)).toBe(true);
    expect(inWindow("22:00", standard)).toBe(false);
  });

  it("handles overnight windows", () => {
    const overnight = { start: "22:00", end: "06:00" };

    expect(inWindow("21:59", overnight)).toBe(false);
    expect(inWindow("22:00", overnight)).toBe(true);
    expect(inWindow("23:59", overnight)).toBe(true);
    expect(inWindow("00:00", overnight)).toBe(true);
    expect(inWindow("05:59", overnight)).toBe(true);
    expect(inWindow("06:00", overnight)).toBe(false);
  });

  it("treats equal start/end as always inside", () => {
    expect(inWindow("00:00", { start: "12:00", end: "12:00" })).toBe(true);
    expect(inWindow("23:59", { start: "12:00", end: "12:00" })).toBe(true);
  });

  it("accepts HH:MM:SS by ignoring seconds", () => {
    expect(inWindow("06:00:00", standard)).toBe(true);
    expect(inWindow("21:59:59", standard)).toBe(true);
    expect(inWindow("22:00:00", standard)).toBe(false);
  });

  it("treats invalid times as inside", () => {
    expect(inWindow("not-a-time", standard)).toBe(true);
    expect(inWindow("24:00", standard)).toBe(true);
    expect(inWindow("12:60", standard)).toBe(true);
    expect(inWindow("", standard)).toBe(true);
  });
});

describe("fullRebuildOutsideWindow", () => {
  const standard = { start: "06:00", end: "22:00" };
  const overnight = { start: "22:00", end: "06:00" };

  it("returns null for null window", () => {
    expect(fullRebuildOutsideWindow(["0 3 * * *"], null)).toBeNull();
  });

  it("returns time of daily cron outside standard window", () => {
    expect(fullRebuildOutsideWindow(["0 3 * * *"], standard)).toBe("03:00");
  });

  it("returns null when daily cron is inside standard window", () => {
    expect(fullRebuildOutsideWindow(["0 7 * * *"], standard)).toBeNull();
  });

  it("handles overnight window correctly", () => {
    expect(fullRebuildOutsideWindow(["0 3 * * *"], overnight)).toBeNull();
    expect(fullRebuildOutsideWindow(["0 12 * * *"], overnight)).toBe("12:00");
  });

  it("respects boundary: start inclusive, end exclusive", () => {
    expect(fullRebuildOutsideWindow(["0 22 * * *"], standard)).toBe("22:00");
    expect(fullRebuildOutsideWindow(["0 6 * * *"], standard)).toBeNull();
  });

  it("treats equal start/end as always inside", () => {
    expect(fullRebuildOutsideWindow(["0 3 * * *"], { start: "12:00", end: "12:00" })).toBeNull();
  });

  it("ignores non-daily crons", () => {
    expect(fullRebuildOutsideWindow(["0 */6 * * *"], standard)).toBeNull();
    expect(fullRebuildOutsideWindow(["*/15 * * * *"], standard)).toBeNull();
    expect(fullRebuildOutsideWindow(["0 * * * *"], standard)).toBeNull();
  });

  it("returns the first outside daily cron", () => {
    expect(
      fullRebuildOutsideWindow(["0 7 * * *", "0 3 * * *", "0 23 * * *"], standard),
    ).toBe("03:00");
    expect(
      fullRebuildOutsideWindow(["0 23 * * *", "0 3 * * *"], standard),
    ).toBe("23:00");
  });

  it("ignores malformed crons", () => {
    expect(fullRebuildOutsideWindow(["not-a-cron"], standard)).toBeNull();
    expect(fullRebuildOutsideWindow([""], standard)).toBeNull();
    expect(fullRebuildOutsideWindow(["0 99 * * *"], standard)).toBeNull();
    expect(fullRebuildOutsideWindow(["60 3 * * *"], standard)).toBeNull();
  });
});

describe("frequencyWords fallback", () => {
  it("falls back to normalised cron when describeCron returns null", () => {
    expect(frequencyWords("*/25 * * * *", null)).toBe("*/25 * * * *");
    expect(frequencyWords("  */25   *  *  *  *  ", null)).toBe("*/25 * * * *");
  });
});
