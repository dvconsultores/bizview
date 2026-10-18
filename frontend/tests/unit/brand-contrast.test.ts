import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

type Triplet = [number, number, number];

const css = readFileSync(join(process.cwd(), "src", "index.css"), "utf8");

const lightCss = css.split(':root[data-theme="dark"]')[0] ?? "";
const darkCss = css.split(':root[data-theme="dark"]')[1] ?? "";

const parseBlock = (block: string): Record<string, string> => {
  const vars: Record<string, string> = {};
  const re = /--([\w-]+):\s*([^;]+);/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(block)) !== null) {
    vars[match[1]] = match[2].trim();
  }
  return vars;
};

const lightVars = parseBlock(lightCss);
const darkVars = parseBlock(darkCss);

const resolveVar = (value: string, vars: Record<string, string>): string => {
  const match = /^var\(--([^)]+)\)$/.exec(value);
  if (!match) return value;
  const name = match[1];
  const resolved = vars[name] ?? lightVars[name] ?? "";
  return resolveVar(resolved, vars);
};

const parseTriplet = (value: string): Triplet => {
  const parts = value.trim().split(/\s+/).map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
    throw new Error(`Invalid RGB triplet: "${value}"`);
  }
  return [parts[0], parts[1], parts[2]];
};

const resolveTriplet = (
  value: string,
  vars: Record<string, string>,
): Triplet => parseTriplet(resolveVar(value, vars));

const srgbLuminance = ([r, g, b]: Triplet): number => {
  const channel = (n: number): number => {
    const s = n / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
};

const contrastRatio = (a: Triplet, b: Triplet): number => {
  const lumA = srgbLuminance(a);
  const lumB = srgbLuminance(b);
  const lighter = Math.max(lumA, lumB);
  const darker = Math.min(lumA, lumB);
  return (lighter + 0.05) / (darker + 0.05);
};

describe("brand-contrast", () => {
  it("white on brand-600 has a contrast ratio of at least 4.5", () => {
    const ratio = contrastRatio([255, 255, 255], resolveTriplet("var(--brand-600)", lightVars));
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("white on brand-700 has a contrast ratio of at least 4.5", () => {
    const ratio = contrastRatio([255, 255, 255], resolveTriplet("var(--brand-700)", lightVars));
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("white on brand-800 has a contrast ratio of at least 4.5", () => {
    const ratio = contrastRatio([255, 255, 255], resolveTriplet("var(--brand-800)", lightVars));
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("light accent on light surface has a contrast ratio of at least 4.5", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-accent)", lightVars),
      resolveTriplet("var(--c-surface)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("dark accent on dark canvas has a contrast ratio of at least 4.5", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-accent)", darkVars),
      resolveTriplet("var(--c-canvas)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("dark accent on dark surface has a contrast ratio of at least 4.5", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-accent)", darkVars),
      resolveTriplet("var(--c-surface)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("field vs surface contrast ratio is at least 1.1 in light mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-field)", lightVars),
      resolveTriplet("var(--c-surface)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(1.1);
  });

  it("field vs surface contrast ratio is at least 1.1 in dark mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-field)", darkVars),
      resolveTriplet("var(--c-surface)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(1.1);
  });

  it("ink on field has a contrast ratio of at least 4.5 in light mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-ink)", lightVars),
      resolveTriplet("var(--c-field)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("ink on field has a contrast ratio of at least 4.5 in dark mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-ink)", darkVars),
      resolveTriplet("var(--c-field)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("on-primary on grad-from has a contrast ratio of at least 4.5 in light mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-on-primary)", lightVars),
      resolveTriplet("var(--grad-from)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("ink-soft on canvas has a contrast ratio of at least 4.5 in light mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-ink-soft)", lightVars),
      resolveTriplet("var(--c-canvas)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("ink-soft on field has a contrast ratio of at least 4.5 in light mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-ink-soft)", lightVars),
      resolveTriplet("var(--c-field)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("accent-strong on field has a contrast ratio of at least 4.5 in light mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-accent-strong)", lightVars),
      resolveTriplet("var(--c-field)", lightVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("accent-strong on field has a contrast ratio of at least 4.5 in dark mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-accent-strong)", darkVars),
      resolveTriplet("var(--c-field)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("brand-100 is not used as a text colour anywhere in src", () => {
    const offenders: string[] = [];
    const srcDir = join(process.cwd(), "src");

    const walk = (dir: string) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(fullPath);
        } else if (entry.isFile() && /\.(ts|tsx)$/.test(entry.name)) {
          const content = readFileSync(fullPath, "utf8");
          if (/\btext-brand-100\b/.test(content)) {
            offenders.push(fullPath);
          }
        }
      }
    };

    walk(srcDir);
    expect(offenders).toEqual([]);
  });

  it("on-primary on grad-from has a contrast ratio of at least 4.5 in dark mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-on-primary)", darkVars),
      resolveTriplet("var(--grad-from)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it("on-primary on grad-to has a contrast ratio of at least 4.5 in dark mode", () => {
    const ratio = contrastRatio(
      resolveTriplet("var(--c-on-primary)", darkVars),
      resolveTriplet("var(--grad-to)", darkVars),
    );
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});
