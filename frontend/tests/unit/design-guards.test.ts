/**
 * Feature 050, FR-009 / SC-002 / SC-008: the rules are guarded, not remembered.
 *
 * Each of the four defects this feature fixed came from a page answering a shared question locally.
 * These checks assert *properties* of the source, not markup snapshots: a narrow page root, a
 * hand-rolled option row, an unbounded split. They are cheap and they fail on the regression, where a
 * pixel diff would fail on a font upgrade instead.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");
const read = (path: string) => readFileSync(join(SRC, path), "utf8");

/** Every page module, so a new one is covered without editing this list. */
function pages(prefix = "pages"): string[] {
  return readdirSync(join(SRC, prefix), { withFileTypes: true }).flatMap((entry) => {
    const path = `${prefix}/${entry.name}`;
    if (entry.isDirectory()) return pages(path);
    return entry.name.endsWith(".tsx") ? [path] : [];
  });
}

const PAGES = pages();

describe("page roots", () => {
  it("loads the page list", () => {
    expect(PAGES.length).toBeGreaterThan(10);
  });

  it("no page constrains its own content width (SC-002)", () => {
    // The container and its gutters come from `lib/layout.ts`; a `max-w-3xl` on a page root is what
    // left Apariencia using a third of a wide screen. Truncation widths (`max-w-[12rem]` on a cell)
    // and a paragraph measure (`max-w-2xl` on a subtitle) are not page widths.
    const pageWidth = /\bmax-w-(?:2xl|3xl|4xl|5xl|6xl|7xl|screen-\w+|prose)\b/;
    const offenders = PAGES.filter((path) => {
      const source = read(path);
      // Only a line that is a bare container gets blamed: it is the wrapper, not a table cell.
      return source.split("\n").some((line) =>
        pageWidth.test(line) && /className=["'`][^"'`]*\b(?:space-y|min-h-screen|pb-)/.test(line));
    });
    expect(offenders, "a page root must use APP_PAGE, never its own max-width").toEqual([]);
  });
});

describe("segmented choices", () => {
  it("the theme and language switches delegate to the one control", () => {
    // The defect was two hand-written copies; one had lost the `grid` that makes the row.
    for (const path of ["components/ThemeSwitcher.tsx", "components/LanguageSwitcher.tsx"]) {
      const source = read(path);
      expect(source, `${path} must use SegmentedControl`).toContain("SegmentedControl");
      expect(source, `${path} must not lay out its own grid`)
        .not.toMatch(/grid-cols-\d/);
    }
  });

  it("the control always renders a grid", () => {
    const source = read("components/SegmentedControl.tsx");
    expect(source).toContain("grid w-fit");
    expect(source).toMatch(/grid-cols-\$\{|COLUMNS\[options\.length\]/);
  });

  it("the appearance library uses the three-column progression (SC-004)", () => {
    const source = read("pages/admin/Appearance.tsx");
    expect(source).toContain("CARD_GRID_3");
    expect(read("lib/layout.ts")).toMatch(/CARD_GRID_3[\s\S]*xl:grid-cols-3/);
  });
});

describe("split panes", () => {
  it("Ayuda bounds both panes and lets each scroll (SC-005)", () => {
    const source = read("pages/Help.tsx");
    expect(source).toContain("SPLIT_COLS");
    expect(source).toContain("PANEL_MAX_H");
    expect(source).toContain("PANEL_SCROLL");
    expect(read("lib/layout.ts")).toMatch(/PANEL_SCROLL = "min-h-0 overflow-y-auto"/);
    expect(read("lib/layout.ts")).toMatch(/PANEL_MAX_H = "lg:max-h-\[calc\(100dvh-/);
  });
});

describe("the layout vocabulary", () => {
  it("is exported from one module and is phone-first", () => {
    const source = read("lib/layout.ts");
    for (const token of ["APP_CONTAINER", "APP_GUTTER", "APP_PAGE", "PAGE_STACK", "CARD_PAD",
                         "PANEL_MAX_H", "PANEL_SCROLL", "SPLIT_COLS", "CARD_GRID_3"]) {
      expect(source, `missing token ${token}`).toContain(token);
    }
    // Base classes are the phone's; enhancements come from `min-width` variants only.
    const appPage = source.slice(source.indexOf("export const APP_PAGE"));
    expect(appPage).not.toMatch(/(?:^|\s)max-(?:w|h)-/);
  });

  it("no screen reads a literal colour (006 / 047, unchanged)", () => {
    const offenders = ["components/SegmentedControl.tsx", "pages/admin/Appearance.tsx",
                       "pages/Help.tsx", "components/PageHeader.tsx"]
      .filter((path) => /(?:bg|text|border|ring)-(?:red|blue|green|gray|slate|zinc|neutral)-\d/.test(read(path)));
    expect(offenders).toEqual([]);
  });
});
