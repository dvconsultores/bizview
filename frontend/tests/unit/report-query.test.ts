import { describe, expect, it } from "vitest";
import type { ReportDefinition } from "../../src/api/types";
import {
  MAX_FILTER_VALUES,
  compareChoices,
  countChanges,
  defaultSelection,
  filterOptionsQuery,
  isIncompleteCustom,
  parseSelection,
  sameSelection,
  selectionQuery,
  serializeSelection,
  validateSelection,
  withFilterValues,
  withoutFilterValue,
} from "../../src/lib/reportQuery";
import type { ReportSelection } from "../../src/lib/reportQuery";

const fixture: ReportDefinition = {
  id: "fixture",
  title: "Fixture",
  description: "Fixture definition",
  icon: null,
  currency: "MXN",
  metrics: {},
  dimensions: {},
  periods: {
    default: "mtd",
    allowed: ["mtd", "last_month", "custom"],
  },
  compare: {
    default: "previous_period",
    allowed: ["previous_period", "previous_year"],
  },
  filters: ["brand", "store"],
  pdf: false,
  ai_narrative: false,
};

const baseSelection: ReportSelection = {
  period: "mtd",
  from: "",
  to: "",
  compare: "previous_period",
  filters: {},
};

describe("reportQuery", () => {
  describe("compareChoices", () => {
    it("returns exactly the allowed values without adding none", () => {
      expect(compareChoices(fixture)).toEqual(["previous_period", "previous_year"]);
    });

    it("dedupes duplicate allowed values", () => {
      const def: ReportDefinition = {
        ...fixture,
        compare: {
          default: "none",
          allowed: ["previous_period", "none", "previous_period"],
        },
      };
      expect(compareChoices(def)).toEqual(["previous_period", "none"]);
    });

    it("returns a single allowed value with matching default", () => {
      const def: ReportDefinition = {
        ...fixture,
        compare: {
          default: "previous_year",
          allowed: ["previous_year"],
        },
      };
      expect(compareChoices(def)).toEqual(["previous_year"]);
    });

    it("prepends default when it is not in allowed", () => {
      const def: ReportDefinition = {
        ...fixture,
        compare: {
          default: "none",
          allowed: ["previous_year"],
        },
      };
      expect(compareChoices(def)).toEqual(["none", "previous_year"]);
    });

    it("returns default when allowed is empty", () => {
      const def: ReportDefinition = {
        ...fixture,
        compare: {
          default: "previous_period",
          allowed: [],
        },
      };
      expect(compareChoices(def)).toEqual(["previous_period"]);
    });

    it("parseSelection falls back to allowed default for disallowed compare values", () => {
      const def: ReportDefinition = {
        ...fixture,
        compare: {
          default: "previous_year",
          allowed: ["previous_year"],
        },
      };
      const params = new URLSearchParams("period=mtd&compare=none");
      const result = parseSelection(params, def);
      expect(result.compare).toBe("previous_year");

      const params2 = new URLSearchParams("period=mtd&compare=previous_period");
      const result2 = parseSelection(params2, def);
      expect(result2.compare).toBe("previous_year");
    });
  });

  describe("defaultSelection", () => {
    it("returns defaults from definition", () => {
      expect(defaultSelection(fixture)).toEqual({
        period: "mtd",
        from: "",
        to: "",
        compare: "previous_period",
        filters: {},
      });
    });
  });

  describe("parseSelection", () => {
    it("returns defaults from empty params", () => {
      const params = new URLSearchParams();
      expect(parseSelection(params, fixture)).toEqual(baseSelection);
    });

    it("parses a legacy single value", () => {
      const params = new URLSearchParams("period=mtd&compare=previous_period&filter.brand=Nike");
      const selection = parseSelection(params, fixture);
      expect(selection.filters).toEqual({ brand: ["Nike"] });
    });

    it("keeps values verbatim, drops empty and duplicates", () => {
      const params = new URLSearchParams();
      params.append("filter.brand", "Nike");
      params.append("filter.brand", "Nike");
      params.append("filter.brand", " Adidas ");
      params.append("filter.brand", "");
      expect(parseSelection(params, fixture).filters).toEqual({ brand: ["Nike", " Adidas "] });
    });

    it("caps filter values at MAX_FILTER_VALUES", () => {
      const params = new URLSearchParams();
      for (let i = 0; i < MAX_FILTER_VALUES + 10; i++) {
        params.append("filter.brand", `v${i}`);
      }
      const selection = parseSelection(params, fixture);
      expect(selection.filters.brand).toHaveLength(MAX_FILTER_VALUES);
      expect(selection.filters.brand[0]).toBe("v0");
      expect(selection.filters.brand[MAX_FILTER_VALUES - 1]).toBe(`v${MAX_FILTER_VALUES - 1}`);
    });

    it("ignores unknown filter ids", () => {
      const params = new URLSearchParams("period=mtd&compare=previous_period&filter.unknown=X&filter.brand=Nike");
      expect(parseSelection(params, fixture).filters).toEqual({ brand: ["Nike"] });
    });

    it("falls back to defaults for invalid period and compare", () => {
      const params = new URLSearchParams("period=bogus&compare=bogus&filter.brand=Nike");
      const selection = parseSelection(params, fixture);
      expect(selection.period).toBe("mtd");
      expect(selection.compare).toBe("previous_period");
      expect(selection.filters).toEqual({ brand: ["Nike"] });
    });

    it("accepts period equal to the default even if not listed as allowed", () => {
      const def: ReportDefinition = {
        ...fixture,
        periods: {
          default: "ytd",
          allowed: ["mtd", "last_month"],
        },
      };
      const params = new URLSearchParams("period=ytd");
      expect(parseSelection(params, def).period).toBe("ytd");
    });

    it("drops from/to unless period is custom", () => {
      const params = new URLSearchParams(
        "period=mtd&compare=previous_period&from=2024-01-01&to=2024-01-31",
      );
      const selection = parseSelection(params, fixture);
      expect(selection.from).toBe("");
      expect(selection.to).toBe("");
    });

    it("keeps valid from/to only when period is custom", () => {
      const params = new URLSearchParams(
        "period=custom&compare=previous_period&from=2024-01-01&to=2024-01-31",
      );
      const selection = parseSelection(params, fixture);
      expect(selection.from).toBe("2024-01-01");
      expect(selection.to).toBe("2024-01-31");
    });

    it("drops invalid from/to formats even for custom", () => {
      const params = new URLSearchParams(
        "period=custom&compare=previous_period&from=01/01/2024&to=abc",
      );
      const selection = parseSelection(params, fixture);
      expect(selection.from).toBe("");
      expect(selection.to).toBe("");
    });
  });

  describe("serializeSelection", () => {
    it("serializes period and compare always", () => {
      const params = serializeSelection(baseSelection, fixture);
      expect(params.get("period")).toBe("mtd");
      expect(params.get("compare")).toBe("previous_period");
    });

    it("includes from/to only when custom and non-empty", () => {
      const custom: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-01",
        to: "",
      };
      const params = serializeSelection(custom, fixture);
      expect(params.get("from")).toBe("2024-01-01");
      expect(params.get("to")).toBeNull();

      const nonCustom: ReportSelection = {
        ...baseSelection,
        from: "2024-01-01",
        to: "2024-01-31",
      };
      const params2 = serializeSelection(nonCustom, fixture);
      expect(params2.get("from")).toBeNull();
      expect(params2.get("to")).toBeNull();
    });

    it("omits ids with empty arrays", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike"], store: [] },
      };
      const params = serializeSelection(selection, fixture);
      expect(params.getAll("filter.brand")).toEqual(["Nike"]);
      expect(params.getAll("filter.store")).toEqual([]);
    });

    it("repeats filter params once per value", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike", "Adidas"] },
      };
      const params = serializeSelection(selection, fixture);
      expect(params.getAll("filter.brand")).toEqual(["Nike", "Adidas"]);
    });

    it("sorts filter ids alphabetically when no def is given", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { zebra: ["z"], apple: ["a"], mango: ["m"] },
      };
      const params = serializeSelection(selection);
      const keys = Array.from(params.keys()).filter((k) => k.startsWith("filter."));
      expect(keys).toEqual(["filter.apple", "filter.mango", "filter.zebra"]);
    });

    it("follows def.filters order when def is given", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { store: ["s1"], brand: ["b1"] },
      };
      const params = serializeSelection(selection, fixture);
      const keys = Array.from(params.keys()).filter((k) => k.startsWith("filter."));
      expect(keys).toEqual(["filter.brand", "filter.store"]);
    });
  });

  describe("selectionQuery", () => {
    it("returns a query string with leading ?", () => {
      expect(selectionQuery(baseSelection, fixture)).toBe(
        "?period=mtd&compare=previous_period",
      );
    });

    it("includes filters", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike"] },
      };
      expect(selectionQuery(selection, fixture)).toBe(
        "?period=mtd&compare=previous_period&filter.brand=Nike",
      );
    });
  });

  describe("filterOptionsQuery", () => {
    it("builds the options query without q when q is blank", () => {
      const query = filterOptionsQuery(baseSelection);
      expect(query).toBe("?period=mtd&compare=none");
    });

    it("includes q trimmed when non-blank", () => {
      const query = filterOptionsQuery(baseSelection, "  Nike Air  ");
      expect(query).toBe("?period=mtd&compare=none&q=Nike+Air");
    });

    it("includes from/to only for custom", () => {
      const custom: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-01",
        to: "2024-01-31",
      };
      const query = filterOptionsQuery(custom);
      expect(query).toBe(
        "?period=custom&from=2024-01-01&to=2024-01-31&compare=none",
      );
    });
  });

  describe("round-trip", () => {
    it("preserves selection through parse(serialize(s)) with special characters", () => {
      const selection: ReportSelection = {
        period: "custom",
        from: "2024-01-01",
        to: "2024-12-31",
        compare: "previous_year",
        filters: {
          brand: ['Ni;ke&Co', "A = B", "café 'au lait'", '"quoted" value'],
          store: ["s1 s2"],
        },
      };
      const params = serializeSelection(selection, fixture);
      const parsed = parseSelection(params, fixture);
      expect(parsed).toEqual(selection);
    });
  });

  describe("sameSelection", () => {
    it("returns true for identical selections", () => {
      expect(sameSelection(baseSelection, baseSelection)).toBe(true);
    });

    it("returns true when filter value order differs", () => {
      const a: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike", "Adidas"] },
      };
      const b: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Adidas", "Nike"] },
      };
      expect(sameSelection(a, b)).toBe(true);
    });

    it("returns false when filter value sets differ", () => {
      const a: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike"] },
      };
      const b: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Adidas"] },
      };
      expect(sameSelection(a, b)).toBe(false);
    });

    it("ignores from/to unless both are custom", () => {
      const a: ReportSelection = { ...baseSelection, from: "2024-01-01", to: "2024-01-31" };
      const b: ReportSelection = { ...baseSelection, from: "2023-01-01", to: "2023-01-31" };
      expect(sameSelection(a, b)).toBe(true);

      const c: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-01",
        to: "2024-01-31",
      };
      const d: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-02",
        to: "2024-01-31",
      };
      expect(sameSelection(c, d)).toBe(false);
    });

    it("treats missing id as empty array", () => {
      const a: ReportSelection = { ...baseSelection, filters: {} };
      const b: ReportSelection = { ...baseSelection, filters: { brand: [] } };
      expect(sameSelection(a, b)).toBe(true);
    });
  });

  describe("countChanges", () => {
    it("counts period, compare, and one filter change as three edits", () => {
      const applied = baseSelection;
      const draft: ReportSelection = {
        ...baseSelection,
        period: "last_month",
        compare: "previous_year",
        filters: { brand: ["Nike"] },
      };
      expect(countChanges(draft, applied)).toBe(3);
    });

    it("counts custom from/to difference as one edit", () => {
      const applied: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-01",
        to: "2024-01-31",
      };
      const draft: ReportSelection = {
        ...applied,
        from: "2024-01-02",
      };
      expect(countChanges(draft, applied)).toBe(1);
    });

    it("counts no changes for order-insensitive filter values", () => {
      const applied: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike", "Adidas"] },
      };
      const draft: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Adidas", "Nike"] },
      };
      expect(countChanges(draft, applied)).toBe(0);
    });
  });


  describe("isIncompleteCustom", () => {
    it("returns false for non-custom", () => {
      expect(isIncompleteCustom(baseSelection)).toBe(false);
    });

    it("returns true when custom and from or to missing", () => {
      expect(
        isIncompleteCustom({ ...baseSelection, period: "custom", from: "", to: "2024-01-31" }),
      ).toBe(true);
      expect(
        isIncompleteCustom({ ...baseSelection, period: "custom", from: "2024-01-01", to: "" }),
      ).toBe(true);
      expect(
        isIncompleteCustom({ ...baseSelection, period: "custom", from: "", to: "" }),
      ).toBe(true);
    });

    it("returns false when custom and both dates present", () => {
      expect(
        isIncompleteCustom({
          ...baseSelection,
          period: "custom",
          from: "2024-01-01",
          to: "2024-01-31",
        }),
      ).toBe(false);
    });
  });

  describe("validateSelection", () => {
    it("returns empty errors for non-custom", () => {
      expect(validateSelection(baseSelection)).toEqual({});
    });

    it("returns missing from error", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "",
        to: "2024-01-31",
      };
      expect(validateSelection(selection)).toEqual({
        from: "Indica la fecha de inicio.",
      });
    });

    it("returns missing to error", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-01",
        to: "",
      };
      expect(validateSelection(selection)).toEqual({
        to: "Indica la fecha de fin.",
      });
    });

    it("returns both missing errors", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "",
        to: "",
      };
      expect(validateSelection(selection)).toEqual({
        from: "Indica la fecha de inicio.",
        to: "Indica la fecha de fin.",
      });
    });

    it("returns to-before-from error", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-02-01",
        to: "2024-01-31",
      };
      expect(validateSelection(selection)).toEqual({
        to: "La fecha final no puede ser anterior a la inicial.",
      });
    });

    it("returns no errors for valid custom range", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        period: "custom",
        from: "2024-01-01",
        to: "2024-01-31",
      };
      expect(validateSelection(selection)).toEqual({});
    });
  });

  describe("withFilterValues", () => {
    it("sets filter values immutably", () => {
      const original = { ...baseSelection };
      const updated = withFilterValues(baseSelection, "brand", ["Nike", "Adidas"]);
      expect(updated.filters).toEqual({ brand: ["Nike", "Adidas"] });
      expect(original.filters).toEqual({});
    });

    it("keeps values verbatim, drops empty and duplicates", () => {
      const updated = withFilterValues(baseSelection, "brand", [" Nike ", "Nike", "", "Adidas"]);
      expect(updated.filters).toEqual({ brand: [" Nike ", "Nike", "Adidas"] });
    });

    it("removes the id when values is empty", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike"], store: ["s1"] },
      };
      const updated = withFilterValues(selection, "brand", []);
      expect(updated.filters).toEqual({ store: ["s1"] });
    });
  });

  describe("withoutFilterValue", () => {
    it("removes a single value immutably", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike", "Adidas"] },
      };
      const updated = withoutFilterValue(selection, "brand", "Nike");
      expect(updated.filters).toEqual({ brand: ["Adidas"] });
      expect(selection.filters).toEqual({ brand: ["Nike", "Adidas"] });
    });

    it("removes the id when the last value is removed", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike"] },
      };
      const updated = withoutFilterValue(selection, "brand", "Nike");
      expect(updated.filters).toEqual({});
    });

    it("does nothing when the value is not present", () => {
      const selection: ReportSelection = {
        ...baseSelection,
        filters: { brand: ["Nike"] },
      };
      const updated = withoutFilterValue(selection, "brand", "Adidas");
      expect(updated.filters).toEqual({ brand: ["Nike"] });
    });
  });
});
