/** Feature 049: what a zip costs, measured the way the server measures it. */
import { describe, expect, it } from "vitest";
import { describeTally, formatSize, tallyIndex } from "../../src/lib/importPreflight";
import type { ImportLimits } from "../../src/api/types";

const LIMITS: ImportLimits = {
  artifacts: { name: "artifacts", max_files: 400, max_kb: 2048, max_mb: 20, label: "specs/" },
  assets: { name: "assets", max_files: 2000, max_kb: 300, max_mb: 25, label: "assets/" },
  zip_max_mb: 45,
  stored: {},
};

const project = (images: number, artifacts: number, prefix = "ventas/") => {
  const entries = [{ name: `${prefix}project.yaml`, size: 100 }];
  for (let i = 1; i < artifacts; i += 1) {
    entries.push({ name: `${prefix}specs/${String(i).padStart(3, "0")}-x/spec.md`, size: 900 });
  }
  for (let i = 0; i < images; i += 1) {
    entries.push({ name: `${prefix}assets/coins/C${i}.png`, size: 3800 });
  }
  return entries;
};

describe("tallyIndex", () => {
  it("counts images apart from the project's own files", () => {
    const result = tallyIndex(project(483, 40), LIMITS);
    expect(result.artifacts.files).toBe(40);
    expect(result.assets.files).toBe(483);
    expect(result.over).toBeNull();
    expect(result.ignored).toEqual([]);
  });

  it("strips the shared top folder before classifying, like the importer", () => {
    const withTop = tallyIndex(project(2, 3, "ventas/"), LIMITS);
    const without = tallyIndex(project(2, 3, ""), LIMITS);
    expect(withTop.assets.files).toBe(without.assets.files);
    expect(withTop.artifacts.files).toBe(without.artifacts.files);
  });

  it("does not strip a layout folder: a zip of the files themselves still classifies", () => {
    const entries = [{ name: "specs/001-x/spec.md", size: 10 },
                     { name: "assets/a.png", size: 10 }];
    const result = tallyIndex(entries, LIMITS);
    expect(result.artifacts.files).toBe(1);
    expect(result.assets.files).toBe(1);
  });

  it("names the images when they are over, and the artifacts when they are", () => {
    expect(tallyIndex(project(2001, 2), LIMITS).over).toBe("assets");
    expect(tallyIndex(project(2, 401), LIMITS).over).toBe("artifacts");
  });

  it("reports both reasons when a tally is over on count and on size", () => {
    const big = [Array.from({ length: 5 }, (_, i) => ({
      name: `assets/${i}.png`, size: 6 * 1024 * 1024 }))].flat();
    expect(tallyIndex(big, LIMITS).assets.over).toEqual(["bytes"]);
  });

  it("puts what belongs to no allowance in the ignored list", () => {
    const entries = [...project(1, 1), { name: "ventas/PROMPT.md", size: 10 },
                     { name: "ventas/request/foto.png", size: 10 },
                     { name: "ventas/.DS_Store", size: 10 }];
    expect(tallyIndex(entries, LIMITS).ignored).toEqual([".DS_Store", "PROMPT.md",
                                                        "request/foto.png"]);
  });

  it("does not count an image outside assets/ against the image allowance", () => {
    const entries = [{ name: "project.yaml", size: 10 }, { name: "docs/foto.png", size: 10 }];
    const result = tallyIndex(entries, LIMITS);
    expect(result.assets.files).toBe(0);
    expect(result.ignored).toEqual(["docs/foto.png"]);
  });
});

describe("the reading of a tally", () => {
  it("counts against the limit and prints a size a person reads", () => {
    const tally = { files: 483, bytes: 1_887_436, over: [] as ("files" | "bytes")[] };
    expect(describeTally(tally, LIMITS.assets)).toBe("483/2000 · 1,8 MB/25 MB");
    expect(formatSize(512)).toBe("1 KB");
    expect(formatSize(26 * 1024 * 1024)).toBe("26,0 MB");
  });
});
