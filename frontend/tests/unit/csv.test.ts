import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CSV_BOM,
  CSV_SEPARATOR,
  csvCell,
  csvFileName,
  downloadCsv,
  toCsv,
  toCsvSections,
  viewCsvTable,
} from "../../src/lib/csv";
import type { CsvColumn, CsvTable } from "../../src/lib/csv";
import type { ReportView } from "../../src/api/types";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("csvCell", () => {
  it("returns empty string for null and undefined", () => {
    expect(csvCell(null)).toBe("");
    expect(csvCell(undefined)).toBe("");
  });

  it("handles booleans", () => {
    expect(csvCell(true)).toBe("true");
    expect(csvCell(false)).toBe("false");
  });

  it("handles numbers with dot decimals", () => {
    expect(csvCell(1234.5)).toBe("1234.5");
    expect(csvCell(-3)).toBe("-3");
    expect(csvCell(1e-7)).toBe("0.0000001");
  });

  it("does not add apostrophe for numbers", () => {
    expect(csvCell(-3)[0]).not.toBe("'");
    expect(csvCell(1234.5)[0]).not.toBe("'");
  });

  it("handles NaN and Infinity as empty string", () => {
    expect(csvCell(NaN)).toBe("");
    expect(csvCell(Infinity)).toBe("");
    expect(csvCell(-Infinity)).toBe("");
  });

  it("does not crash on large numbers", () => {
    expect(typeof csvCell(1e21)).toBe("string");
  });

  it("quotes strings containing separator", () => {
    expect(csvCell(`a${CSV_SEPARATOR}b`)).toBe(`"a${CSV_SEPARATOR}b"`);
  });

  it("doubles double quotes", () => {
    expect(csvCell('a"b')).toBe('"a""b"');
  });

  it("quotes strings containing newlines", () => {
    expect(csvCell("a\nb")).toBe('"a\nb"');
    expect(csvCell("a\rb")).toBe('"a\rb"');
  });

  it("quotes strings with leading/trailing spaces", () => {
    expect(csvCell(" a")).toBe('" a"');
    expect(csvCell("a ")).toBe('"a "');
  });

  it("guards formula-injection strings with apostrophe", () => {
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(csvCell("-x")).toBe("'-x");
    expect(csvCell("@x")).toBe("'@x");
    expect(csvCell("+x")).toBe("'+x");
  });

  it("keeps accents intact", () => {
    expect(csvCell("Café Ñandú")).toBe("Café Ñandú");
  });

  it("formats Date at local midnight as YYYY-MM-DD", () => {
    const date = new Date(2026, 8, 1);
    expect(csvCell(date)).toBe("2026-09-01");
  });

  it("formats Date with time as ISO string", () => {
    const date = new Date(2026, 8, 1, 12, 30, 0);
    expect(csvCell(date)).toBe(date.toISOString());
  });

  it("keeps ISO date strings unchanged", () => {
    expect(csvCell("2026-09-01T00:00:00.000Z")).toBe("2026-09-01T00:00:00.000Z");
  });

  it("numbers through toCsv avoid apostrophe (numeric ranking key)", () => {
    const columns: CsvColumn[] = [{ id: "key", label: "Clave" }];
    const csv = toCsv(columns, [{ key: 2026 }], { bom: false });
    expect(csv).toBe("Clave\r\n2026\r\n");
  });

  it("string dimension values starting with '-' get apostrophe guard", () => {
    const columns: CsvColumn[] = [{ id: "key", label: "Clave" }];
    const csv = toCsv(columns, [{ key: "-5" }], { bom: false });
    expect(csv).toBe("Clave\r\n'-5\r\n");
  });
});

describe("toCsv", () => {
  const columns: CsvColumn[] = [
    { id: "name", label: "Nombre" },
    { id: "value", label: "Valor" },
  ];

  it("includes BOM by default", () => {
    const csv = toCsv(columns, [{ name: "Nike", value: 100 }]);
    expect(csv.startsWith(CSV_BOM)).toBe(true);
  });

  it("omits BOM with bom: false", () => {
    const csv = toCsv(columns, [{ name: "Nike", value: 100 }], { bom: false });
    expect(csv.startsWith(CSV_BOM)).toBe(false);
  });

  it("uses semi-colon separator, labels as header, and CRLF line endings", () => {
    const csv = toCsv(columns, [{ name: "Nike", value: 100 }]);
    expect(csv).toBe(`${CSV_BOM}Nombre;Valor\r\nNike;100\r\n`);
  });

  it("handles missing cell values as empty", () => {
    const csv = toCsv(columns, [{}]);
    expect(csv).toBe(`${CSV_BOM}Nombre;Valor\r\n;\r\n`);
  });
});

describe("toCsvSections", () => {
  it("produces a single BOM, titles, and blank lines between tables", () => {
    const tables: CsvTable[] = [
      {
        title: "Ventas",
        columns: [{ id: "brand", label: "Marca" }],
        rows: [{ brand: "Nike" }],
      },
      {
        title: "Tiendas",
        columns: [{ id: "store", label: "Tienda" }],
        rows: [{ store: "Centro" }],
      },
    ];
    const csv = toCsvSections(tables);
    expect(csv.startsWith(CSV_BOM)).toBe(true);
    expect(csv.indexOf(CSV_BOM)).toBe(csv.lastIndexOf(CSV_BOM));
    expect(csv).toBe(
      `${CSV_BOM}Ventas\r\nMarca\r\nNike\r\n\r\nTiendas\r\nTienda\r\nCentro\r\n`,
    );
  });

  it("quotes title lines when necessary", () => {
    const tables: CsvTable[] = [
      {
        title: "V;ntas",
        columns: [{ id: "brand", label: "Marca" }],
        rows: [],
      },
    ];
    const csv = toCsvSections(tables);
    expect(csv).toBe(`${CSV_BOM}"V;ntas"\r\nMarca\r\n`);
  });
});

describe("viewCsvTable", () => {
  it("returns table view with title fallback to Detalle", () => {
    const view: ReportView = {
      type: "table",
      title: null,
      columns: [
        { id: "brand", label: "Marca", kind: "dimension" },
        { id: "sales", label: "Ventas", kind: "metric", format: "currency" },
      ],
      rows: [{ brand: "Nike", sales: 100 }],
    };
    const table = viewCsvTable(view);
    expect(table?.title).toBe("Detalle");
    expect(table?.columns).toEqual([
      { id: "brand", label: "Marca" },
      { id: "sales", label: "Ventas" },
    ]);
    expect(table?.rows).toEqual([{ brand: "Nike", sales: 100 }]);
  });

  it("returns ranking without previous/change when no previous data", () => {
    const view: ReportView = {
      type: "ranking",
      metric: "sales",
      dimension: "brand",
      title: "Marcas",
      label: "Ventas",
      dimension_label: "Marca",
      format: "currency",
      items: [
        { key: "Nike", value: 100, share: 50, previous: null, change: null },
      ],
    };
    const table = viewCsvTable(view);
    expect(table?.title).toBe("Marcas");
    expect(table?.columns).toEqual([
      { id: "key", label: "Marca" },
      { id: "value", label: "Ventas" },
      { id: "share", label: "Participación (%)" },
    ]);
    expect(table?.rows).toEqual([
      { key: "Nike", value: 100, share: 50 },
    ]);
  });

  it("returns ranking with previous/change when previous data exists", () => {
    const view: ReportView = {
      type: "ranking",
      metric: "sales",
      dimension: "brand",
      title: "Marcas",
      label: "Ventas",
      dimension_label: "Marca",
      format: "currency",
      items: [
        { key: "Nike", value: 100, share: 50, previous: 80, change: { pct: 25, new: false } },
      ],
    };
    const table = viewCsvTable(view);
    expect(table?.columns).toEqual([
      { id: "key", label: "Marca" },
      { id: "value", label: "Ventas" },
      { id: "share", label: "Participación (%)" },
      { id: "previous", label: "Período anterior" },
      { id: "change", label: "Variación (%)" },
    ]);
    expect(table?.rows).toEqual([
      { key: "Nike", value: 100, share: 50, previous: 80, change: 25 },
    ]);
  });

  it("returns null for kpis and trend", () => {
    expect(viewCsvTable({ type: "kpis", items: [] })).toBeNull();
    expect(
      viewCsvTable({
        type: "trend",
        metric: "sales",
        label: "Ventas",
        format: "currency",
        grain: "month",
        points: [],
      }),
    ).toBeNull();
  });
});

describe("csvFileName", () => {
  it("slugs the base name", () => {
    expect(csvFileName("Ventas por Tienda — Sept")).toBe("ventas-por-tienda-sept.csv");
  });

  it("removes accents", () => {
    expect(csvFileName("Café Ñandú")).toBe("cafe-nandu.csv");
  });

  it("falls back to reporte for empty slugs", () => {
    expect(csvFileName("!!!")).toBe("reporte.csv");
  });
});

describe("downloadCsv", () => {
  it("triggers an anchor download and revokes the object URL after 1000ms", () => {
    vi.useFakeTimers();
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const createObjectURL = vi.fn(() => "blob:csv");
    const revokeObjectURL = vi.fn();
    let clicked: HTMLAnchorElement | undefined;

    (URL as unknown as { createObjectURL: typeof URL.createObjectURL }).createObjectURL =
      createObjectURL;
    (URL as unknown as { revokeObjectURL: typeof URL.revokeObjectURL }).revokeObjectURL =
      revokeObjectURL;

    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicked = this;
      });

    try {
      downloadCsv("reporte.csv", "a;b\r\n");

      expect(createObjectURL).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);

      expect(clicked).toBeDefined();
      expect(clicked?.download).toBe("reporte.csv");
      expect(clicked?.href).toContain("blob:csv");
      expect(clicked?.isConnected).toBe(false);

      expect(revokeObjectURL).not.toHaveBeenCalled();

      vi.advanceTimersByTime(1000);
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:csv");
      expect(document.querySelector("a[download='reporte.csv']")).toBeNull();
    } finally {
      (URL as unknown as { createObjectURL: typeof URL.createObjectURL }).createObjectURL =
        originalCreateObjectURL;
      (URL as unknown as { revokeObjectURL: typeof URL.revokeObjectURL }).revokeObjectURL =
        originalRevokeObjectURL;
      vi.useRealTimers();
    }
  });
});
