import { describe, expect, it } from "vitest";
import { toggledCrossFilter } from "../../src/components/report/crossFilter";

// Feature 063 — one plain click is one cross-filter; Ctrl/Cmd-click combines.
describe("cross-filter toggle", () => {
  it("replaces the filter when another dimension is clicked", () => {
    expect(toggledCrossFilter({ product: ["A"] }, "client", "B", false)).toEqual({ client: ["B"] });
  });

  it("replaces a multi-value selection with the clicked value", () => {
    expect(toggledCrossFilter({ product: ["A", "B"] }, "product", "A", false)).toEqual({ product: ["A"] });
  });

  it("removes the only selected value when it is clicked again", () => {
    expect(toggledCrossFilter({ product: ["A"] }, "product", "A", false)).toEqual({});
  });

  it("adds and removes a value with Ctrl/Cmd inside its dimension", () => {
    expect(toggledCrossFilter({ product: ["A"] }, "product", "B", true)).toEqual({ product: ["A", "B"] });
    expect(toggledCrossFilter({ product: ["A", "B"] }, "product", "A", true)).toEqual({ product: ["B"] });
  });

  it("keeps the other dimensions when Ctrl/Cmd combines them", () => {
    expect(toggledCrossFilter({ product: ["A"] }, "client", "B", true)).toEqual({
      product: ["A"],
      client: ["B"],
    });
  });
});
