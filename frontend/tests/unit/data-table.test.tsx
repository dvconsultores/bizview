import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReportDefinition, ReportView } from "../../src/api/types";
import { CardDataTable } from "../../src/components/report/CardDataTable";
import { viewDataTable } from "../../src/lib/dataTable";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const def: ReportDefinition = {
  id: "ventas", title: "Ventas", description: "", icon: null, currency: "USD",
  metrics: { net_sales: { label: "Ventas netas", format: "currency", better: "higher" } },
  dimensions: { product: { label: "Producto" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "previous_period", allowed: ["none", "previous_period"] },
  filters: [], pdf: true,
};

const ranking: ReportView = {
  type: "ranking", id: "productos", metric: "net_sales", dimension: "product",
  title: "Ventas por producto", label: "Ventas netas", dimension_label: "Producto",
  format: "currency", summary: "",
  items: [
    { key: "Alimento", value: 40, share: 40, previous: 20, change: { pct: 100, new: false } },
    { key: "Vacuna", value: 25, share: 25, previous: null, change: null },
  ],
};

const table: ReportView = {
  type: "table", id: "detalle", title: "Detalle", summary: "",
  columns: [
    { id: "product", label: "Producto", kind: "dimension" },
    { id: "net_sales", label: "Ventas netas", kind: "metric", format: "currency" },
    { id: "orders", label: "Pedidos", kind: "metric", format: "integer" },
  ],
  rows: [{ product: "Alimento", net_sales: 10, orders: 2 }],
};

const trend: ReportView = {
  type: "trend", id: "tendencia", metric: "net_sales", label: "Ventas netas",
  format: "currency", grain: "month", summary: "",
  points: [{ bucket: "2026-09-01", value: 10, previous: 8 }],
};

describe("viewDataTable (feature 064)", () => {
  it("keeps the chart order and adds comparison and share columns", () => {
    const model = viewDataTable(ranking, { def })!;
    expect(model.title).toBe("Ventas por producto");
    expect(model.columns.map((column) => column.label)).toEqual([
      "Producto", "Ventas netas", t.reportParams.display.previousPeriodColumn,
      t.reportParams.display.changeColumn, "% del total",
    ]);
    expect(model.rows.map((row) => row.values[0])).toEqual(["Alimento", "Vacuna"]);
    expect(model.rows[0].value).toBe("Alimento");
  });

  it("honours the component's column order and titles a table", () => {
    const model = viewDataTable(table, { def, component: { id: "t", type: "table", view: "detalle", columns: ["orders", "product"], title: "Detalle de pedidos" } })!;
    expect(model.title).toBe("Detalle de pedidos");
    expect(model.columns.map((column) => column.id)).toEqual(["orders", "product"]);
    expect(model.rows[0].values).toEqual([2, "Alimento"]);
  });

  it("writes one row per trend bucket and keeps the previous series", () => {
    const model = viewDataTable(trend, { def })!;
    expect(model.columns.map((column) => column.id)).toEqual(["bucket", "net_sales", "net_sales:previous"]);
    expect(model.rows[0].values).toEqual(["2026-09-01", 10, 8]);
  });

  it("never uses a component id as the title", () => {
    const model = viewDataTable({ ...ranking, title: undefined, label: "Ventas netas" }, {
      def, component: { id: "productos", type: "bar", view: "productos" },
    })!;
    expect(model.title).not.toBe("productos");
  });
});

let container: HTMLDivElement;
const mounted: { root: Root; node: HTMLDivElement }[] = [];

beforeEach(() => {
  navigator.clipboard = { writeText: vi.fn().mockResolvedValue(undefined) } as unknown as Clipboard;
});

afterEach(async () => {
  for (const entry of mounted.splice(0)) {
    await act(async () => entry.root.unmount());
    entry.node.remove();
  }
});

function mount(node: ReactNode): HTMLDivElement {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push({ root, node: host });
  act(() => root.render(node));
  container = host;
  return host;
}

describe("CardDataTable full rows (feature 064)", () => {
  it("asks for the uncut view when the payload says it was truncated", async () => {
    const fetchFull = vi.fn().mockResolvedValue({ ...ranking, truncated: false });
    mount(<CardDataTable view={{ ...ranking, truncated: true }} options={{ def }} currency="USD"
                          fetchFull={fetchFull} />);
    const button = Array.from(container.querySelectorAll("button"))
      .find((entry) => entry.textContent?.includes(t.reportParams.dataTable.fullRows))!;
    expect(button).toBeTruthy();
    await act(async () => button.click());
    expect(fetchFull).toHaveBeenCalledTimes(1);
  });
});

describe("CardDataTable", () => {
  it("searches accent-insensitively and copies the filtered TSV", async () => {
    mount(<CardDataTable view={ranking} options={{ def }} currency="USD" />);
    const search = container.querySelector("input[type=search]") as HTMLInputElement;
    act(() => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      setter.call(search, "vacuna");
      search.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(container.textContent).toContain(t.reportParams.dataTable.rows(1));
    const copy = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent?.includes(t.reportParams.dataTable.copy))!;
    await act(async () => copy.click());
    const [text] = (navigator.clipboard.writeText as unknown as { mock: { calls: string[][] } }).mock.calls[0];
    expect(text.replace(/\u00a0/g, " ")).toBe(
      "Producto\tVentas netas\tPeríodo anterior\tVariación (%)\t% del total\nVacuna\t25,00 USD\t—\t—\t25 %",
    );
  });
});
