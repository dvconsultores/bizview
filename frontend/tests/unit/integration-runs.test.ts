import { describe, expect, it } from "vitest";
import { datasetSummary, formatMs, pathLabel, rollupSummary } from "../../src/lib/integrationRuns";

describe("rollupSummary", () => {
  it("returns null when rollups is empty or undefined", () => {
    expect(rollupSummary(undefined)).toBeNull();
    expect(rollupSummary({})).toBeNull();
  });

  it("returns updated text for all ok rollups", () => {
    const summary = rollupSummary({ "ventas-dia": { ok: true, mode: "full", rows: 10 } });
    expect(summary).toBe("Resumen diario actualizado");
  });

  it("returns failed ids for failed rollups", () => {
    const summary = rollupSummary({ "ventas-dia": { ok: false, error: "boom" } });
    expect(summary).toBe("Resumen diario no actualizado: ventas-dia");
  });

  it("joins updated and failed with separator", () => {
    const summary = rollupSummary({
      "a": { ok: true },
      "b": { ok: false, error: "x" },
      "c": { ok: true },
    });
    expect(summary).toBe("2 resúmenes diarios actualizados · Resumen diario no actualizado: b");
  });
});

describe("pathLabel", () => {
  it("labels all known paths", () => {
    expect(pathLabel("copy")).toBe("COPY");
    expect(pathLabel("bulk")).toBe("COPY");
    expect(pathLabel("copy+polars")).toBe("COPY + Polars");
    expect(pathLabel("rows")).toBe("filas");
    expect(pathLabel("rows+polars")).toBe("filas + Polars");
  });

  it("returns null for missing path", () => {
    expect(pathLabel(undefined)).toBeNull();
  });
});

describe("formatMs", () => {
  it("formats milliseconds", () => {
    expect(formatMs(0)).toBe("0 ms");
    expect(formatMs(999)).toBe("999 ms");
    expect(formatMs(2500)).toBe("2,5 s");
    expect(formatMs(10000)).toBe("10,0 s");
  });
});

describe("datasetSummary", () => {
  it("basic dataset with written rows", () => {
    expect(datasetSummary("ventas", { extracted: 10, written: 10, full: false }))
      .toBe("ventas: 10 filas");
  });

  it("full + fallback", () => {
    expect(
      datasetSummary("ventas", {
        extracted: 10,
        written: 10,
        full: true,
        path: "rows",
        fallback: "feature_not_supported",
      })
    ).toBe("ventas: 10 filas (completa) · filas · sin COPY (feature_not_supported)");
  });

  it("transform mode rows with ms duration", () => {
    expect(
      datasetSummary("ventas", {
        extracted: 10,
        written: 10,
        full: false,
        path: "rows+polars",
        transform_mode: "rows",
        transform_ms: 42,
      })
    ).toBe("ventas: 10 filas · filas + Polars · Polars por lotes 42 ms");
  });

  it("transform mode rows with seconds duration and input rows", () => {
    expect(
      datasetSummary("ventas", {
        extracted: 10,
        written: 10,
        full: false,
        path: "rows+polars",
        transform_mode: "rows",
        transform_ms: 2500,
        rows_in: 15,
      })
    ).toBe(
      "ventas: 10 filas · filas + Polars · Polars por lotes 2,5 s (15 filas de entrada)"
    );
  });

  it("rows_in equal to extracted is omitted", () => {
    expect(
      datasetSummary("ventas", {
        extracted: 10,
        written: 10,
        full: false,
        path: "rows+polars",
        transform_mode: "rows",
        transform_ms: 42,
        rows_in: 10,
      })
    ).toBe("ventas: 10 filas · filas + Polars · Polars por lotes 42 ms");
  });
});
