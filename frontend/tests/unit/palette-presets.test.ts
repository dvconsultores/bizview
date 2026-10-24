/**
 * Feature 030 gate (FR-010, SC-004): every palette preset passes, in both themes, the contrast and
 * distinguishability rules of `specs/030-report-page-polish/contracts/palette-preset.md`; the PDF's
 * mirror is byte-identical; and no report definition in the repository carries a colour literal
 * (026 FR-005 still holds).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRESET,
  effectivePreset,
  isPaletteId,
  PALETTES,
  paletteVariables,
  PRESET_IDS,
} from "../../src/theme/palette";

const ROOT = join(process.cwd(), "..");
const FRONTEND_DIR = join(process.cwd(), "src", "theme", "palettes");
const BACKEND_DIR = join(ROOT, "backend", "app", "reports", "palettes");

type Triplet = [number, number, number];

const srgb = (hex: string): Triplet => {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16)) as Triplet;
};
const channel = (n: number): number => {
  const s = n / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const luminance = (hex: string): number => {
  const [r, g, b] = srgb(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
};
const contrast = (a: string, b: string): number => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const lab = (hex: string): Triplet => {
  const [r, g, b] = srgb(hex).map(channel) as Triplet;
  const x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047;
  const y = r * 0.2126 + g * 0.7152 + b * 0.0722;
  const z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
  const f = (t: number) => (t > 0.008856 ? t ** (1 / 3) : 7.787 * t + 16 / 116);
  const [fx, fy, fz] = [f(x), f(y), f(z)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
};
const deltaE = (a: string, b: string): number => {
  const [la, lb] = [lab(a), lab(b)];
  return Math.hypot(la[0] - lb[0], la[1] - lb[1], la[2] - lb[2]);
};

const HEX = /^#[0-9A-F]{6}$/;
const ROLES = [
  "primary",
  ...Array.from({ length: 8 }, (_, i) => `series${i + 1}`),
  "positive",
  "negative",
  "neutral",
  "grid",
  "surface",
  "kpi_text",
] as const;

/** The minimum contrast of a series against the card surface, per the contract. */
const minSeriesContrast = (presetId: string): number => (presetId === "contraste" ? 7 : 3);
/** `monocromo` is a single-hue ramp: it is checked on lightness steps instead of ΔE. */
const minAdjacentDelta = (strategy: string): number => (strategy === "sequential" ? 5 : 10);

describe("palette presets (feature 030)", () => {
  it("ships the five presets, each complete in both themes", () => {
    expect([...PRESET_IDS].sort()).toEqual([...Object.keys(PALETTES)].sort());
    expect(PRESET_IDS).toHaveLength(5);
    expect(isPaletteId(DEFAULT_PRESET)).toBe(true);
    for (const id of PRESET_IDS) {
      const preset = PALETTES[id];
      expect(preset.id, id).toBe(id);
      expect(preset.label_key, id).toBe(`palette.${id}`);
      expect(["categorical", "sequential"], id).toContain(preset.strategy);
      for (const theme of ["light", "dark"] as const) {
        const values = preset[theme];
        for (const role of ROLES) {
          expect(values[role], `${id}.${theme}.${role}`).toMatch(HEX);
        }
        expect(values.kpi_delta_bg.positive, `${id}.${theme}.kpi_delta_bg`).toMatch(HEX);
        expect(values.kpi_delta_bg.negative, `${id}.${theme}.kpi_delta_bg`).toMatch(HEX);
      }
    }
  });

  it("every preset passes contrast and distinguishability in both themes", () => {
    const problems: string[] = [];
    for (const id of PRESET_IDS) {
      const preset = PALETTES[id];
      const floor = minSeriesContrast(id);
      const adjacent = minAdjacentDelta(preset.strategy);
      for (const theme of ["light", "dark"] as const) {
        const t = preset[theme];
        const surface = t.surface;
        const series = Array.from({ length: 8 }, (_, i) => t[`series${i + 1}` as const]);
        series.forEach((colour, index) => {
          const ratio = contrast(colour, surface);
          if (ratio < floor) {
            problems.push(`${id}/${theme}: series${index + 1} ${colour} is ${ratio.toFixed(2)}:1 (< ${floor}:1)`);
          }
        });
        if (preset.strategy === "sequential") {
          const lightness = series.map((colour) => lab(colour)[0]);
          const ascending = lightness.every((value, i) => i === 0 || value > lightness[i - 1]);
          const descending = lightness.every((value, i) => i === 0 || value < lightness[i - 1]);
          if (!ascending && !descending) problems.push(`${id}/${theme}: the ramp is not monotonic`);
          const steps = lightness.slice(1).map((value, i) => Math.abs(value - lightness[i]));
          steps.forEach((step, index) => {
            if (step < adjacent) {
              problems.push(`${id}/${theme}: L* step ${index + 1}→${index + 2} is ${step.toFixed(1)} (< ${adjacent})`);
            }
          });
        } else {
          for (let i = 0; i < series.length - 1; i += 1) {
            const distance = deltaE(series[i], series[i + 1]);
            if (distance < adjacent) {
              problems.push(`${id}/${theme}: series${i + 1}/series${i + 2} ΔE ${distance.toFixed(1)} (< ${adjacent})`);
            }
          }
        }
        for (const role of ["positive", "negative"] as const) {
          const ratio = contrast(t[role], surface);
          if (ratio < floor) problems.push(`${id}/${theme}: ${role} ${ratio.toFixed(2)}:1 (< ${floor}:1)`);
        }
        if (deltaE(t.positive, t.negative) < 25) {
          problems.push(`${id}/${theme}: positive and negative are too close (${deltaE(t.positive, t.negative).toFixed(1)})`);
        }
        if (contrast(t.kpi_text, surface) < 4.5) {
          problems.push(`${id}/${theme}: kpi_text ${contrast(t.kpi_text, surface).toFixed(2)}:1 (< 4.5:1, AA)`);
        }
        for (const role of ["positive", "negative"] as const) {
          const ratio = contrast(t[role], t.kpi_delta_bg[role]);
          if (ratio < 4.5) problems.push(`${id}/${theme}: delta badge ${role} ${ratio.toFixed(2)}:1 (< 4.5:1)`);
        }
        if (contrast(t.grid, surface) >= 1.8) {
          problems.push(`${id}/${theme}: grid ${contrast(t.grid, surface).toFixed(2)}:1 is not subtle (< 1.8:1)`);
        }
      }
    }
    expect(problems, problems.join("\n")).toEqual([]);
  });

  it("maps every role to a CSS custom property", () => {
    const vars = paletteVariables(PALETTES.impacto, "light");
    for (const name of [
      ...Array.from({ length: 8 }, (_, i) => `chart-${i + 1}`),
      "chart-positive",
      "chart-negative",
      "chart-neutral",
      "chart-grid",
      "chart-label",
      "kpi-text",
      "kpi-surface",
      "kpi-neutral",
      "kpi-delta-bg-positive",
      "kpi-delta-bg-negative",
    ]) {
      expect(vars[name], name).toMatch(/^\d{1,3} \d{1,3} \d{1,3}$/);
    }
  });

  it("keeps the PDF mirror byte-identical", () => {
    const mirrored = readdirSync(BACKEND_DIR).filter((file) => file.endsWith(".json")).sort();
    expect(mirrored).toEqual(PRESET_IDS.map((id) => `${id}.json`).sort());
    for (const file of mirrored) {
      expect(
        readFileSync(join(BACKEND_DIR, file), "utf8"),
        `${file}: frontend/src/theme/palettes and backend/app/reports/palettes must match`,
      ).toBe(readFileSync(join(FRONTEND_DIR, file), "utf8"));
    }
  });

  it("resolves report override → installation → impacto", () => {
    expect(effectivePreset("contraste", "clasico")).toBe("contraste");
    expect(effectivePreset(null, "clasico")).toBe("clasico");
    expect(effectivePreset(undefined, undefined)).toBe(DEFAULT_PRESET);
    expect(effectivePreset("neon", "neon")).toBe(DEFAULT_PRESET);
    expect(effectivePreset("neon", "daltonico")).toBe("daltonico");
  });
});

/** SC-004: no report definition in the repository carries a hex colour (026 FR-005). */
describe("no colour literals in report definitions", () => {
  // `projects/` and `artemisa/` are local customer workspaces (outside the product, principle VII).
  const SKIP = new Set([
    "node_modules", ".git", "dist", "build", "__pycache__", "specs", "attachments", "projects", "artemisa",
  ]);

  function definitionFiles(dir: string, out: string[] = []): string[] {
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return out; // unreadable folder: nothing to check there
    }
    for (const entry of entries) {
      if (SKIP.has(entry) || entry.startsWith(".")) continue;
      const path = join(dir, entry);
      const stats = statSync(path);
      if (stats.isDirectory()) definitionFiles(path, out);
      else if (/\.(ya?ml|json)$/.test(entry)) out.push(path);
    }
    return out;
  }

  it("every layout in a definition uses roles, never hex", () => {
    const offenders: string[] = [];
    for (const file of definitionFiles(ROOT)) {
      const text = readFileSync(file, "utf8");
      if (!/^\s*layout:/m.test(text)) continue;
      text.split("\n").forEach((line, index) => {
        if (/#[0-9a-fA-F]{3,8}\b/.test(line) && !line.trimStart().startsWith("#")) {
          offenders.push(`${relative(ROOT, file)}:${index + 1} ${line.trim()}`);
        }
      });
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});
