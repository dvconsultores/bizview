/**
 * Feature 047 gate: the built-in themes are themes like any other — complete in both modes, inside
 * the shape lists, and passing the accessibility rules a customer's uploaded file is held to. The
 * mathematics here mirrors `cli/bizview_cli/theme.py`; `theme-parity` in the backend suite asserts
 * the two agree on the six built-ins, so a change on one side without the other fails.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  BUILTIN_THEMES,
  DEFAULT_THEME,
  deriveTokens,
  isThemeId,
  SHAPE_DEFAULTS,
  shapeVariables,
  THEME_IDS,
  type Theme,
} from "../../src/theme/themes";

const ROOT = join(process.cwd(), "..");
const FRONTEND_DIR = join(process.cwd(), "src", "theme", "themes");
const BACKEND_DIR = join(ROOT, "backend", "app", "reports", "themes");
const SCHEMA = join(ROOT, "cli", "bizview_cli", "schemas", "theme.schema.json");

const HEX = /^#[0-9A-Fa-f]{6}$/;
const COLOUR_TOKENS = [
  "surface", "card", "text", "muted", "grid", "primary", "positive", "negative", "neutral",
  "delta_positive", "delta_negative",
] as const;
const SHAPE_LISTS: Record<string, readonly string[]> = {
  radius: ["sm", "md", "lg"],
  density: ["compact", "normal"],
  kpi_scale: ["md", "lg", "xl"],
  font: ["sans", "serif", "mono"],
  badge: ["filled", "outline"],
  // Feature 051: the dimensions a theme differs on beyond colour.
  elevation: ["flat", "soft", "strong"],
  button: ["rounded", "pill", "square"],
  nav: ["gradient", "solid", "bar", "outline"],
  divider: ["soft", "strong"],
  heading: ["normal", "tight"],
  card_border: ["none", "hairline", "strong"],
};

const srgb = (hex: string): [number, number, number] => {
  const v = hex.replace("#", "");
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
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
const labL = (hex: string): number => {
  const [r, g, b] = srgb(hex).map(channel) as [number, number, number];
  const y = r * 0.2126 + g * 0.7152 + b * 0.0722;
  return 116 * (y > 0.008856 ? y ** (1 / 3) : 7.787 * y + 16 / 116) - 16;
};
const lab = (hex: string): [number, number, number] => {
  const [r, g, b] = srgb(hex).map(channel) as [number, number, number];
  const x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047;
  const y = r * 0.2126 + g * 0.7152 + b * 0.0722;
  const z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
  const f = (v: number) => (v > 0.008856 ? v ** (1 / 3) : 7.787 * v + 16 / 116);
  return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))];
};
const deltaE = (a: string, b: string): number =>
  Math.hypot(...(lab(a).map((v, i) => v - lab(b)[i]) as [number, number, number]));

describe("themes as data (feature 047)", () => {
  it("ships the six built-ins, each complete in both modes", () => {
    expect(THEME_IDS).toHaveLength(6);
    expect(isThemeId(DEFAULT_THEME)).toBe(true);
    for (const id of THEME_IDS) {
      const theme = BUILTIN_THEMES[id];
      expect(theme.id, id).toBe(id);
      expect(theme.name.length, id).toBeGreaterThan(0);
      expect(theme.name_en.length, id).toBeGreaterThan(0);
      expect(theme.version, id).toBeGreaterThanOrEqual(1);
      for (const mode of ["light", "dark"] as const) {
        const tokens = theme[mode];
        for (const role of COLOUR_TOKENS) {
          expect(tokens[role], `${id}.${mode}.${role}`).toMatch(HEX);
        }
        expect(tokens.series.length, `${id}.${mode}.series`).toBeGreaterThanOrEqual(3);
        expect(tokens.series.length, `${id}.${mode}.series`).toBeLessThanOrEqual(8);
        for (const colour of tokens.series) expect(colour, `${id}.${mode}`).toMatch(HEX);
      }
      for (const [key, allowed] of Object.entries(SHAPE_LISTS)) {
        const value = (theme.shape ?? {})[key as keyof typeof SHAPE_LISTS];
        if (value !== undefined) expect(allowed, `${id}.shape.${key}`).toContain(value);
      }
    }
  });

  it("keeps the authored schema and the built-ins describing the same tokens", () => {
    const schema = JSON.parse(readFileSync(SCHEMA, "utf8"));
    expect(schema.additionalProperties).toBe(false);
    expect(new Set(schema.required)).toEqual(
      new Set(["id", "name", "name_en", "version", "light", "dark"]),
    );
    const mode = schema.properties.light;
    expect(mode.additionalProperties).toBe(false);
    expect([...mode.required].sort()).toEqual([...COLOUR_TOKENS, "series"].sort());
    expect(mode.properties.series.minItems).toBe(3);
    expect(mode.properties.series.maxItems).toBe(8);
    expect(Object.keys(schema.properties.shape.properties).sort()).toEqual(
      Object.keys(SHAPE_LISTS).sort(),
    );
    for (const [key, allowed] of Object.entries(SHAPE_LISTS)) {
      expect(schema.properties.shape.properties[key].enum, key).toEqual([...allowed]);
    }
    // and the default shape uses only values the schema allows
    for (const [key, value] of Object.entries(SHAPE_DEFAULTS)) {
      expect(SHAPE_LISTS[key], key).toContain(value);
    }
  });

  it("holds every built-in to the accessibility rules, in both modes", () => {
    const problems: string[] = [];
    for (const id of THEME_IDS) {
      const theme = BUILTIN_THEMES[id];
      const floor = id === "contraste" ? 7 : 3;
      const sequential = theme.strategy === "sequential";
      for (const mode of ["light", "dark"] as const) {
        const t = theme[mode];
        const where = `${id}/${mode}`;
        if (contrast(t.text, t.surface) < 4.5) {
          problems.push(`${where}: text ${contrast(t.text, t.surface).toFixed(2)}:1 (< 4.5:1)`);
        }
        t.series.forEach((colour, index) => {
          const ratio = contrast(colour, t.surface);
          if (ratio < floor) problems.push(`${where}: series${index + 1} ${ratio.toFixed(2)}:1`);
        });
        for (const role of ["positive", "negative"] as const) {
          const ratio = contrast(t[role], t.surface);
          if (ratio < floor) problems.push(`${where}: ${role} ${ratio.toFixed(2)}:1`);
          const badge = contrast(t[role], t[`delta_${role}` as "delta_positive"]);
          if (badge < 4.5) problems.push(`${where}: badge ${role} ${badge.toFixed(2)}:1`);
        }
        if (deltaE(t.positive, t.negative) < 25) {
          problems.push(`${where}: positive/negative ΔE ${deltaE(t.positive, t.negative)}`);
        }
        if (contrast(t.grid, t.surface) >= 1.8) {
          problems.push(`${where}: grid ${contrast(t.grid, t.surface).toFixed(2)}:1 is not subtle`);
        }
        if (sequential) {
          for (let i = 0; i < t.series.length - 1; i += 1) {
            const step = Math.abs(labL(t.series[i + 1]) - labL(t.series[i]));
            if (step < 5) problems.push(`${where}: L* step ${i + 1} is ${step.toFixed(1)}`);
          }
        } else {
          for (let i = 0; i < t.series.length - 1; i += 1) {
            const distance = deltaE(t.series[i], t.series[i + 1]);
            if (distance < 10) {
              problems.push(`${where}: series${i + 1}/${i + 2} ΔE ${distance.toFixed(1)}`);
            }
          }
        }
      }
    }
    expect(problems, problems.join("\n")).toEqual([]);
  });

  it("derives every runtime role from the authored tokens", () => {
    for (const id of THEME_IDS) {
      const theme = BUILTIN_THEMES[id] as Theme;
      for (const mode of ["light", "dark"] as const) {
        const tokens = theme[mode];
        const runtime = deriveTokens(theme, mode);
        expect(runtime.kpi_text).toBe(tokens.text);
        expect(runtime.kpi_delta_bg.positive).toBe(tokens.delta_positive);
        expect(runtime.kpi_delta_bg.negative).toBe(tokens.delta_negative);
        expect(runtime.surface).toBe(tokens.surface);
        // eight roles, the last one repeating when the theme declares fewer
        for (let index = 0; index < 8; index += 1) {
          const expected = tokens.series[Math.min(index, tokens.series.length - 1)];
          expect(runtime[`series${index + 1}` as "series1"], `${id}/${mode}/${index}`).toBe(expected);
        }
      }
    }
  });

  it("maps the shape tokens to the custom properties components read", () => {
    // Clásico is the neutral reference for each enum's default.
    const vars = shapeVariables(BUILTIN_THEMES.clasico);
    expect(vars["t-radius"]).toBe("8px");
    expect(vars["t-density"]).toBe("1");
    expect(vars["t-kpi-scale"]).toBe("1.25");
    expect(vars["t-font"]).toContain("sans-serif");
    expect(vars["t-badge"]).toBe("filled");
    const compact = shapeVariables({
      ...BUILTIN_THEMES.clasico,
      shape: { radius: "lg", density: "compact", kpi_scale: "xl", font: "mono", badge: "outline" },
    });
    expect(compact["t-radius"]).toBe("14px");
    expect(compact["t-badge"]).toBe("outline");
  });

  it("keeps the PDF mirror byte-identical", () => {
    const mirrored = readdirSync(BACKEND_DIR).filter((file) => file.endsWith(".json")).sort();
    expect(mirrored).toEqual(THEME_IDS.map((id) => `${id}.json`).sort());
    for (const file of mirrored) {
      expect(
        readFileSync(join(BACKEND_DIR, file), "utf8"),
        `${file}: frontend/src/theme/themes and backend/app/reports/themes must match`,
      ).toBe(readFileSync(join(FRONTEND_DIR, file), "utf8"));
    }
  });
});
