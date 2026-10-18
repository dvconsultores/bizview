import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? sourceFiles(p) : /\.tsx?$/.test(f) ? [p] : [];
  });
}

const DIALOG = /role\s*=\s*["']dialog["']|role\s*:\s*["']dialog["']/i;
const ARIAMODAL = /aria-modal/i;
const MODAL_IMPORT = /from\s+["'][^"']*components\/Modal["']|components\/Modal/i;
const FIXED_INSET = /fixed\s+inset-0/;

describe("modal contract guard", () => {
  it("no Modal.tsx or forbidden modal patterns in src", () => {
    const violations: string[] = [];
    for (const file of sourceFiles(SRC)) {
      const rel = relative(process.cwd(), file);
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        const n = i + 1;
        if (DIALOG.test(line)) violations.push(`${rel}:${n} role="dialog"`);
        if (ARIAMODAL.test(line)) violations.push(`${rel}:${n} aria-modal`);
        if (MODAL_IMPORT.test(line)) violations.push(`${rel}:${n} components/Modal import`);
        if (FIXED_INSET.test(line)) violations.push(`${rel}:${n} fixed inset-0`);
      });
    }
    expect(violations, violations.join("\n")).toEqual([]);
  });

  it("Modal.tsx no longer exists", () => {
    expect(existsSync(join(SRC, "components", "Modal.tsx"))).toBe(false);
  });
});
