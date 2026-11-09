import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Feature 062, FR-012: the two layout patterns that made four of the five defects invisible.
 *
 * - `sticky bottom-20` was the floating action bar of the source form. It was right before the
 *   shell had a bottom tab bar and wrong after; on a phone it covered the fields it saves. The
 *   actions now scroll with the form, and this gate is what keeps a copy of the pattern from
 *   creeping back into an admin form.
 * - `writing-mode` (rotated text) was what 059's sweep looked for when a title printed one letter
 *   per line. The real cause was a `min-w-0 flex-1` box squeezed by non-shrinking buttons, so the
 *   gate also refuses a title inside a flex row without `min-w-0`, which is the shape that bites.
 */

const SRC = join(process.cwd(), "src");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory() ? sourceFiles(path) : /\.tsx?$/.test(entry) ? [path] : [];
  });
}

describe("layout guards (feature 062)", () => {
  it("has no floating action bar left in src", () => {
    // The pattern is only a defect in a class list; a comment that names it is documentation (and
    // this file's own docstring does). So the match is anchored on `class`/`className`.
    const pattern = /(?:class|className)\s*=\s*["'`][^"'`]*\bsticky\s+bottom-20\b/;
    const violations: string[] = [];
    for (const file of sourceFiles(SRC)) {
      const text = readFileSync(file, "utf8");
      for (const match of text.matchAll(new RegExp(pattern.source, "g"))) {
        const line = text.slice(0, match.index).split("\n").length;
        violations.push(`${relative(process.cwd(), file)}:${line} sticky bottom-20`);
      }
    }
    expect(violations, violations.join("\n")).toEqual([]);
  });

  it("never rotates text to make it fit", () => {
    const violations: string[] = [];
    for (const file of sourceFiles(SRC)) {
      readFileSync(file, "utf8").split("\n").forEach((line, index) => {
        if (/writing-mode/.test(line)) {
          violations.push(`${relative(process.cwd(), file)}:${index + 1} writing-mode`);
        }
      });
    }
    expect(violations, violations.join("\n")).toEqual([]);
  });

  it("gives every dialog header title a min-w-0 box, so it cannot be squeezed to one character", () => {
    const dialog = readFileSync(
      join(SRC, "components", "report", "CardDialog.tsx"),
      "utf8",
    );
    const heading = /<h2[^>]*id=\{titleId\}[\s\S]{0,200}?className="([^"]+)"/.exec(dialog);
    expect(heading, "the dialog header must keep its <h2>").not.toBeNull();
    expect(heading![1]).toContain("min-w-0");
    // It truncates instead of wrapping: `[overflow-wrap:anywhere]` is what printed one letter per
    // line when the flex row left the box a sliver of width.
    expect(heading![1]).toContain("truncate");
    expect(heading![1]).not.toContain("overflow-wrap:anywhere");
  });
});
