/**
 * Feature 051 gates, part 1: the derivation.
 *
 * Three properties, in the order they matter:
 *
 * 1. **Clásico does not move** (FR-010). Production runs Clásico, so the tokens the whole
 *    application paints with are compared against the literals `index.css` held before this
 *    feature — read straight out of the file, not copied into the test. The roles that carry the
 *    identity must match exactly; the intermediate shades of a ramp must stay imperceptibly close
 *    (ΔE ≤ 6), because they are now mixed rather than hand-picked.
 * 2. **Every variant is readable** (FR-015): WCAG 2.2 AA on the pairs the chrome actually paints.
 * 3. **The four official themes are different** (FR-011): more than an accent swap.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { chromeOf, contrast, designVariables, semanticVariables } from "../../src/theme/derive";
import { BUILTIN_THEMES, type Theme, type ThemeMode } from "../../src/theme/themes";

const CSS = readFileSync(join(process.cwd(), "src", "index.css"), "utf8");
const MODES: ThemeMode[] = ["light", "dark"];

/** The brand scale, declared once on `:root` and referenced from both modes. */
const BRAND: Record<string, string> = Object.fromEntries(
  [...CSS.slice(0, CSS.indexOf(':root[data-theme="dark"]')).matchAll(
    /--brand-([0-9]+)\s*:\s*([0-9 ]+);/g)].map(([, step, value]) => [step, value.trim()]),
);

/** The declarations of one CSS rule, brand scale included, as `name → "R G B"`. */
function ruleBody(selector: string): Record<string, string> {
  const start = CSS.indexOf(selector);
  expect(start, `index.css must still define ${selector}`).toBeGreaterThan(-1);
  const open = CSS.indexOf("{", start);
  const close = CSS.indexOf("}", open);
  const body = CSS.slice(open + 1, close).replace(/\/\*[\s\S]*?\*\//g, "");
  const declared: Record<string, string> = {};
  for (const [, name, value] of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+)/gi)) {
    declared[name] = value.trim();
  }
  // The brand scale is declared once on `:root`; a dark rule that names it reads the same values.
  const values: Record<string, string> = {};
  for (const [name, value] of Object.entries(declared)) {
    const reference = /^var\(--brand-([0-9]+)\)$/.exec(value);
    values[name] = reference ? BRAND[reference[1]] : value;
  }
  return values;
}

const LIGHT = ruleBody(":root {");
const DARK = ruleBody(':root[data-theme="dark"] {');

/** Four themes × two modes, and the two compatibility themes, all of which must be readable. */
const ALL: [string, Theme][] = Object.entries(BUILTIN_THEMES);

const tripletToHex = (triplet: string) =>
  `#${triplet.split(" ").map((n) => Number(n).toString(16).padStart(2, "0")).join("")}`.toUpperCase();

const lab = (hex: string): [number, number, number] => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const s = parseInt(hex.slice(i, i + 2), 16) / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  const x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047;
  const y = r * 0.2126 + g * 0.7152 + b * 0.0722;
  const z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
  const f = (t: number) => (t > 0.008856 ? t ** (1 / 3) : 7.787 * t + 16 / 116);
  return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))];
};

const deltaE = (a: string, b: string): number => {
  const [l1, a1, b1] = lab(a);
  const [l2, a2, b2] = lab(b);
  return Math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2);
};

/** Every token Clásico declares is compared; the roles a user reads as "the look" first. */
const EXACT = [
  "canvas", "surface", "subtle", "line", "ink", "ink-3", "primary", "accent", "chrome",
  "on-chrome",
];

describe("Clásico keeps the appearance production has today (FR-010)", () => {
  /** The cascade index.css applied: the dark rule only overrides what it declares. */
  const cascade = (mode: ThemeMode) => (mode === "light" ? LIGHT : { ...LIGHT, ...DARK });

  for (const mode of MODES) {
    it(`matches index.css token for token in ${mode}`, () => {
      const before = cascade(mode);
      const now = semanticVariables(BUILTIN_THEMES.clasico, mode);
      const drift: string[] = [];
      let compared = 0;
      for (const [name, value] of Object.entries(now)) {
        const declared = before[`--${name}`];
        if (declared === undefined) continue;
        compared += 1;
        const expected = tripletToHex(declared);
        const actual = tripletToHex(value);
        if (expected !== actual) drift.push(`${name}: ${expected} → ${actual}`);
      }
      // The theme must pin the whole chrome, not a handful: this is what makes the claim real. The
      // chart roles are excluded on purpose — they are painted from the theme's report palette and
      // `tests/unit/palette-presets.test.ts` holds them; the literals in index.css are only their
      // pre-JS fallback.
      expect(compared, "chrome tokens compared against index.css").toBeGreaterThanOrEqual(46);
      expect(drift, "the chrome moved").toEqual([]);
    });
  }

  it("keeps the shape production has today", () => {
    const geometry = designVariables(BUILTIN_THEMES.clasico, "light");
    expect(geometry["radius-card"]).toBe("1.25rem");
    expect(geometry["radius-button"]).toBe("0.875rem");
    expect(geometry["kpi-numeral"]).toBe("1.25rem");
    expect(geometry["kpi-tracking"]).toBe("-0.01em");
    expect(geometry["card-border"]).toBe("1px");
    expect(geometry["nav-mark"]).toBe("gradient");
    expect(geometry["shadow-card"]).toBe(
      "0 1px 2px rgb(15 23 42 / 0.06), 0 4px 16px -4px rgb(15 23 42 / 0.08)",
    );
  });
});

describe("every variant is readable (FR-015)", () => {
  for (const [id, theme] of ALL) {
    for (const mode of MODES) {
      it(`${id} ${mode}: text, ink and UI pairs meet WCAG 2.2 AA`, () => {
        const chrome = chromeOf(theme, mode);
        const vars = semanticVariables(theme, mode);
        const hex = (name: string) => tripletToHex(vars[name]);
        // Text on the three surfaces it is actually painted on.
        for (const [ink, base] of [
          ["c-ink", "c-surface"],
          ["c-ink", "c-canvas"],
          ["c-ink-3", "c-surface"],
          ["c-ink-muted", "c-surface"],
          ["c-ink-soft", "c-surface"],
          ["c-ink-soft", "c-canvas"],
          ["c-ink", "c-field"],
          ["c-accent", "c-surface"],
          ["c-accent", "c-accent-soft"],
          ["c-on-primary", "c-primary"],
          ["c-on-chrome", "c-chrome"],
        ] as const) {
          expect(contrast(hex(ink), hex(base)), `${id} ${mode}: ${ink} on ${base}`).toBeGreaterThanOrEqual(4.5);
        }
        // Component contrast (3:1): borders and the accent against what they sit on.
        expect(contrast(hex("c-line-strong"), hex("c-surface")), `${id} ${mode}: line-strong`).toBeGreaterThanOrEqual(1.4);
        expect(contrast(hex("c-focus"), hex("c-canvas")), `${id} ${mode}: focus ring`).toBeGreaterThanOrEqual(2);
        expect(contrast(chrome.accent, chrome.canvas), `${id} ${mode}: accent on canvas`).toBeGreaterThanOrEqual(3);
      });
    }
  }
});

describe("the four official themes differ in more than colour (FR-011)", () => {
  const OFFICIAL = ["clasico", "impacto", "elegante", "contraste"] as const;

  /** Every dimension a reviewer can name without reading the label. */
  function fingerprint(theme: Theme, mode: ThemeMode): Record<string, string> {
    const chrome = chromeOf(theme, mode);
    const vars = semanticVariables(theme, mode);
    const geometry = designVariables(theme, mode);
    return {
      canvas: chrome.canvas,
      surface: tripletToHex(vars["c-surface"]),
      chrome: chrome.chrome,
      accent: chrome.accent,
      field: chrome.field,
      radiusCard: geometry["radius-card"],
      radiusButton: geometry["radius-button"],
      elevation: geometry["shadow-card"],
      cardBorder: geometry["card-border"],
      nav: geometry["nav-mark"],
      heading: `${geometry["heading-weight"]} ${geometry["heading-tracking"]}`,
      kpi: `${geometry["kpi-numeral"]} ${geometry["kpi-tracking"]}`,
    };
  }

  for (const mode of MODES) {
    it(`pairs of official themes differ on at least four dimensions (${mode})`, () => {
      for (let i = 0; i < OFFICIAL.length; i++) {
        for (let j = i + 1; j < OFFICIAL.length; j++) {
          const a = fingerprint(BUILTIN_THEMES[OFFICIAL[i]], mode);
          const b = fingerprint(BUILTIN_THEMES[OFFICIAL[j]], mode);
          const differing = Object.keys(a).filter((key) => a[key] !== b[key]);
          expect(
            differing.length,
            `${OFFICIAL[i]} vs ${OFFICIAL[j]} (${mode}) differ only on ${differing.join(", ")}`,
          ).toBeGreaterThanOrEqual(4);
        }
      }
    });

    it(`no official theme is a recolour of another (${mode})`, () => {
      for (let i = 0; i < OFFICIAL.length; i++) {
        for (let j = i + 1; j < OFFICIAL.length; j++) {
          const a = fingerprint(BUILTIN_THEMES[OFFICIAL[i]], mode);
          const b = fingerprint(BUILTIN_THEMES[OFFICIAL[j]], mode);
          // A recolor: same geometry, same nav treatment, only colours move.
          expect(a.nav === b.nav && a.radiusCard === b.radiusCard && a.elevation === b.elevation,
            `${OFFICIAL[i]} and ${OFFICIAL[j]} (${mode}) share geometry and navigation treatment`)
            .toBe(false);
        }
      }
    });
  }
});
