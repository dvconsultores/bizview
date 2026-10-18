import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/** Feature 006 guard (contracts/theme-tokens.md): screens use semantic colour tokens, so every
 * screen works in both themes. Raw palette utilities and colour literals are refused, except
 * the fixed surfaces listed below. */
const SRC = join(process.cwd(), "src");   // vitest runs from frontend/

const RAW = /(?<![\w-])(?:[a-z-]+:)*(?:bg|text|border|ring|divide|fill|stroke|placeholder|from|via|to|outline|decoration|shadow|caret|accent)-(?:white|black|slate|gray|zinc|neutral|stone|brand|rose|red|emerald|green|amber|yellow|orange|blue|sky|indigo|violet|purple|pink|teal|cyan|lime)(?:-\d{2,3})?(?:\/\d+)?(?![\w-])/g;
const LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(/g;

// Allowed raw utilities: they sit on surfaces that are the same in both themes.
const ALLOWED: Record<string, { classes: string[]; reason: string }> = {
  "text-white": { classes: ["text-white"], reason: "text on solid primary/danger fills, the hero and the toast" },
  hero: { classes: ["bg-white/15", "ring-white/30", "hover:bg-white/10", "text-brand-50", "text-brand-100"], reason: "hero gradient header (fixed in both themes)" },
  knob: { classes: ["bg-white"], reason: "switch knob stays white on its coloured track" },
  toast: { classes: ["text-emerald-400", "text-amber-300"], reason: "toast is dark in both themes" },
};
const ALLOWED_BY_FILE: Record<string, string[]> = {
  "components/Switch.tsx": ["bg-white"],
  "components/Toast.tsx": ["text-emerald-400", "text-amber-300"],
  "components/Logo.tsx": ["bg-white"],  // fixed light tile behind a customer logo on the gradient
};
// Colour literals: the browser bar colour must be known before any CSS loads (theme-init.js).
const LITERALS_BY_FILE: Record<string, string[]> = { "theme/resolve.ts": ["#3a7393", "#172b37"] };
const GLOBAL_ALLOWED = new Set([...ALLOWED["text-white"].classes, ...ALLOWED.hero.classes]);

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? sourceFiles(p) : /\.tsx?$/.test(f) ? [p] : [];
  });
}

describe("colour guard (feature 006)", () => {
  it("screens use theme tokens, not raw palette colours or colour literals", () => {
    const offending: string[] = [];
    for (const file of sourceFiles(SRC)) {
      const rel = relative(SRC, file);
      const fileAllowed = new Set(ALLOWED_BY_FILE[rel] ?? []);
      readFileSync(file, "utf8").split("\n").forEach((line, i) => {
        for (const m of line.matchAll(RAW)) {
          if (!GLOBAL_ALLOWED.has(m[0]) && !fileAllowed.has(m[0])) offending.push(`${rel}:${i + 1} ${m[0]}`);
        }
        for (const m of line.matchAll(LITERAL)) {
          if (!(LITERALS_BY_FILE[rel] ?? []).includes(m[0])) offending.push(`${rel}:${i + 1} ${m[0]}`);
        }
      });
    }
    expect(offending, "use a token from contracts/theme-tokens.md instead").toEqual([]);
  });

  it("every token used in the code is defined for both themes", () => {
    const css = readFileSync(join(SRC, "index.css"), "utf8");
    const [light, dark] = css.split(':root[data-theme="dark"]');
    const config = readFileSync(join(process.cwd(), "tailwind.config.js"), "utf8");
    const tokens = [...config.matchAll(/"([a-z0-9-]+)"/g)].map((m) => m[1])
      .filter((n) => light.includes(`--c-${n}:`));
    expect(tokens.length).toBeGreaterThan(40);
    const fixed = new Set(["primary", "primary-hover", "primary-active", "focus", "danger-solid",
      "danger-solid-hover", "danger-solid-active"]);   // same colour in both themes by design
    const missing = tokens.filter((n) => !fixed.has(n) && !dark.includes(`--c-${n}:`));
    expect(missing).toEqual([]);
  });
});
