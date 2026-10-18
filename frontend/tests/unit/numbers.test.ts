import { afterEach, describe, expect, it } from "vitest";
import { changeTone, formatChange, formatRange, formatValue } from "../../src/lib/numbers";
import { activate } from "../../src/i18n/live";

const clean = (s: string) => s.replace(/ | /g, " ");

describe("report number formatting (matches the PDF)", () => {
  it("formats metric kinds in Spanish", () => {
    expect(clean(formatValue(11.75, "currency", "USD"))).toBe("11,75 USD");
    expect(clean(formatValue(12345, "integer"))).toBe("12.345");
    expect(clean(formatValue(12.5, "percent"))).toBe("12,5 %");
    expect(formatValue(null, "currency")).toBe("—");
    expect(formatValue("P1", "text")).toBe("P1");
  });

  it("describes changes with a zero base as new", () => {
    expect(formatChange({ pct: null, new: true })).toBe("Nuevo");
    expect(clean(formatChange({ pct: 12.345, new: false }))).toBe("+12,3 %");
    expect(formatChange(null)).toBe("—");
  });

  it("colours changes by the metric's better direction", () => {
    expect(changeTone({ pct: 5, new: false }, "higher")).toBe("good");
    expect(changeTone({ pct: 5, new: false }, "lower")).toBe("bad");
    expect(changeTone({ pct: 0, new: false })).toBe("flat");
    expect(changeTone({ pct: null, new: true })).toBe("flat");
  });

  it("never shifts ISO dates across time zones", () => {
    expect(formatRange({ from: "2026-09-01", to: "2026-09-01" })).toMatch(/^1 sept? 2026$/);
    expect(formatRange({ from: "2026-09-01", to: "2026-09-29" })).toContain("29");
  });
});

describe("English formatting (feature 022)", () => {
  afterEach(() => activate("es"));

  it("formats numbers in English", () => {
    activate("en");
    expect(clean(formatValue(11.75, "currency", "USD"))).toBe("USD 11.75");
    expect(formatValue(12345, "integer")).toBe("12,345");
    expect(formatValue(12.5, "percent")).toBe("12.5%");
  });

  it("formats changes in English", () => {
    activate("en");
    expect(formatChange({ new: true, pct: null })).toBe("New");
    expect(formatChange({ new: false, pct: 12.345 })).toBe("+12.3%");
  });

  it("formats dates in English and switches back", () => {
    activate("en");
    expect(formatRange({ from: "2026-09-01", to: "2026-09-01" })).toBe("Sep 1, 2026");
    activate("es");
    expect(formatValue(12345, "integer")).toBe("12.345");
  });
});
