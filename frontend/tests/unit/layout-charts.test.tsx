import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ReportData, ReportDefinition, ReportView, WebComponent } from "../../src/api/types";
import { LayoutRenderer } from "../../src/components/report/LayoutRenderer";
import { t } from "../../src/i18n/es";

// Feature 026 — US1: the layout's chart kinds (line, area, bar, pie, donut, sparkline).

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

let container: HTMLDivElement;
const mounted: { root: Root; node: HTMLDivElement }[] = [];

beforeEach(() => {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
});

afterEach(async () => {
  for (const entry of mounted.splice(0)) {
    await act(async () => {
      entry.root.unmount();
    });
    entry.node.remove();
  }
});

/** A fresh container per chart, so a second case never inherits the first one's DOM. */
function mount(node: ReactNode): HTMLDivElement {
  const node_ = document.createElement("div");
  document.body.appendChild(node_);
  const root = createRoot(node_);
  mounted.push({ root, node: node_ });
  act(() => {
    root.render(node);
  });
  return node_;
}

const def: ReportDefinition = {
  id: "ventas",
  title: "Ventas",
  description: "Resumen de ventas",
  icon: null,
  currency: "USD",
  metrics: {
    net_sales: { label: "Ventas netas", format: "currency", better: "higher" },
    orders: { label: "Pedidos", format: "integer", better: "higher" },
  },
  dimensions: { product: { label: "Producto" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "previous_period", allowed: ["none", "previous_period"] },
  filters: ["product"],
  pdf: true,
  ai_narrative: false,
};

const daily: ReportView = {
  type: "trend",
  id: "diaria",
  metric: "net_sales",
  label: "Ventas netas",
  format: "currency",
  grain: "day",
  summary: "Ventas netas por día: máximo 30,00 USD el 3 de septiembre.",
  points: [
    { bucket: "2026-09-01", value: 10, previous: 5 },
    { bucket: "2026-09-02", value: null, previous: null },
    { bucket: "2026-09-03", value: 30, previous: 12 },
  ],
};

const continuous: ReportView = {
  type: "trend",
  id: "continua",
  metric: "net_sales",
  label: "Ventas netas",
  format: "currency",
  grain: "day",
  summary: "Ventas netas por día del 1 al 3 de septiembre de 2026.",
  points: [
    { bucket: "2026-09-01", value: 10 },
    { bucket: "2026-09-02", value: 20 },
    { bucket: "2026-09-03", value: 30 },
  ],
};

const kpis: ReportView = {
  type: "kpis",
  id: "resumen",
  summary: "Ventas netas de 100,00 USD en el período.",
  items: [
    {
      metric: "net_sales",
      label: "Ventas netas",
      format: "currency",
      better: "higher",
      value: 100,
      previous: 80,
      change: { pct: 25, new: false },
    },
  ],
};

const marcas: ReportView = {
  type: "table",
  id: "marcas",
  title: "Marcas",
  summary: "Ventas netas y pedidos por marca.",
  columns: [
    { id: "product", label: "Producto", kind: "dimension" },
    { id: "net_sales", label: "Ventas netas", kind: "metric", format: "currency" },
    { id: "orders", label: "Pedidos", kind: "metric", format: "integer" },
  ],
  rows: [
    { product: "Alimento premium", net_sales: 10, orders: 2 },
    { product: "Vacuna triple", net_sales: 20, orders: 4 },
  ],
};

const eight: ReportView = {
  type: "table",
  id: "ocho-marcas",
  title: "Ocho marcas",
  summary: "Ventas netas de ocho marcas.",
  columns: [
    { id: "product", label: "Producto", kind: "dimension" },
    { id: "net_sales", label: "Ventas netas", kind: "metric", format: "currency" },
  ],
  rows: Array.from({ length: 8 }, (_, index) => ({ product: `Marca ${index + 1}`, net_sales: 100 })),
};

const single: ReportView = {
  type: "table",
  id: "una-marca",
  title: "Una marca",
  summary: "Ventas netas de una sola marca.",
  columns: [
    { id: "product", label: "Producto", kind: "dimension" },
    { id: "net_sales", label: "Ventas netas", kind: "metric", format: "currency" },
  ],
  rows: [{ product: "Alimento premium", net_sales: 100 }],
};

const productos: ReportView = {
  type: "ranking",
  id: "productos",
  metric: "net_sales",
  dimension: "product",
  title: "Ventas por producto",
  label: "Ventas netas",
  dimension_label: "Producto",
  format: "currency",
  summary: "Ventas netas por producto: Alimento premium encabeza el ranking.",
  items: [
    { key: "Alimento premium", value: 40, share: 40, previous: null, change: null },
    { key: "Vacuna triple", value: 25, share: 25, previous: null, change: null },
    { key: "Antibiótico", value: 15, share: 15, previous: null, change: null },
    { key: "Desparasitante", value: 12, share: 12, previous: null, change: null },
    { key: "Vitaminas", value: 8, share: 8, previous: null, change: null },
  ],
};

const data: ReportData = {
  selection: {
    period: "mtd",
    current: { from: "2026-09-01", to: "2026-09-30" },
    compare: "previous_period",
    previous: { from: "2026-08-01", to: "2026-08-31" },
    partial: false,
    grain: "day",
  },
  filters: {},
  freshness: { updated_at: null, data_version: "v1" },
  views: [kpis, daily, continuous, marcas, single, eight, productos],
};

function render(component: WebComponent, source: ReportData = data): HTMLDivElement {
  container = mount(<LayoutRenderer layout={{ components: [component] }} data={source} def={def} />);
  return container;
}

const rects = () => Array.from(container.querySelectorAll("rect"));
const rectBoxes = () =>
  rects().map((rect) => ({
    x: Number(rect.getAttribute("x")),
    y: Number(rect.getAttribute("y")),
    width: Number(rect.getAttribute("width")),
    height: Number(rect.getAttribute("height")),
  }));

describe("line and area", () => {
  it("keeps the current and the previous series, with the null gaps, in the declared roles", () => {
    render({ id: "diaria", type: "line", view: "diaria", colors: ["series3", "series4"] });
    const paths = Array.from(container.querySelectorAll("path"));

    expect(paths).toHaveLength(2);
    expect(paths[0].getAttribute("class")).toContain("stroke-chart-3");
    expect(paths[0].getAttribute("stroke-dasharray")).toBeNull();
    // A gap reopens the path with a second M instead of bridging it.
    expect(paths[0].getAttribute("d")?.match(/M/g)).toHaveLength(2);

    expect(paths[1].getAttribute("class")).toContain("stroke-chart-4");
    expect(paths[1].getAttribute("stroke-dasharray")).toBe("4 3");
    expect(container.querySelector("figcaption")?.textContent).toBe(daily.summary);
  });

  it("falls back to the current-period role when the layout declares none", () => {
    render({ id: "diaria", type: "line", view: "diaria" });
    const paths = Array.from(container.querySelectorAll("path"));
    expect(paths[0].getAttribute("class")).toContain("stroke-chart-1");
    expect(paths[1].getAttribute("class")).toContain("stroke-chart-2");
  });

  it("fills the current series for area, and never bridges a gap with the fill", () => {
    render({ id: "area", type: "area", view: "continua", colors: ["series1"] });
    const filled = Array.from(container.querySelectorAll("path")).filter(
      (path) => path.getAttribute("fill-opacity") === "0.12",
    );
    expect(filled).toHaveLength(1);
    expect(filled[0].getAttribute("d")?.endsWith("Z")).toBe(true);

    render({ id: "area", type: "area", view: "diaria", colors: ["series1"] });
    const gapped = Array.from(container.querySelectorAll("path")).filter(
      (path) => path.getAttribute("fill-opacity") === "0.12",
    );
    expect(gapped).toHaveLength(0);
  });
});

describe("bar", () => {
  it("draws one bar per series and category when it is grouped", () => {
    render({ id: "barras", type: "bar", view: "marcas", x: "product", series: ["net_sales", "orders"] });
    const boxes = rectBoxes();

    expect(boxes).toHaveLength(4);
    expect(new Set(boxes.map((box) => box.width)).size).toBe(1);
    expect(new Set(boxes.map((box) => box.x)).size).toBe(4);
  });

  it("stacks the series of a category on top of each other", () => {
    render({ id: "barras", type: "bar", view: "marcas", x: "product", series: ["net_sales", "orders"], stacked: true });
    const boxes = rectBoxes();

    expect(boxes).toHaveLength(4);
    const [first, second] = boxes;
    expect(second.x).toBe(first.x);
    expect(second.width).toBe(first.width);
    expect(boxes[2].x).not.toBe(first.x);
    expect(new Set(boxes.map((box) => box.x)).size).toBe(2);
    // The segments of one bar meet: the lower one ends where the upper one starts.
    expect(second.y + second.height).toBeCloseTo(first.y, 6);
  });

  it("draws horizontal bars whose length follows the value", () => {
    render({ id: "ancho", type: "bar", view: "marcas", x: "product", series: ["net_sales"], orientation: "horizontal" });
    const boxes = rectBoxes();
    expect(boxes).toHaveLength(2);
    expect(boxes[1].width / boxes[0].width).toBeCloseTo(2, 6);
    expect(boxes[1].y).toBeGreaterThan(boxes[0].y);
  });

  it("reads the orientation from the layout", () => {
    render({ id: "alta", type: "bar", view: "ocho-marcas", x: "product", series: ["net_sales"] });
    const vertical = rectBoxes()[0];
    expect(vertical.height).toBeGreaterThan(vertical.width);

    render({
      id: "largo",
      type: "bar",
      view: "ocho-marcas",
      x: "product",
      series: ["net_sales"],
      orientation: "horizontal",
    });
    const horizontal = rectBoxes()[0];
    expect(horizontal.width).toBeGreaterThan(horizontal.height);
  });

  it("keeps the top_n categories and drops the tail", () => {
    render({ id: "top", type: "bar", view: "productos", category: "product", value: "net_sales", top_n: 2 });
    expect(rects()).toHaveLength(2);
  });

  it("renders the error card when the declared series is not the view's metric", () => {
    render({ id: "barras", type: "bar", view: "productos", series: ["orders"] });
    expect(container.textContent).toContain(t.layout.missingMetric("barras", "orders"));
    expect(rects()).toHaveLength(0);
  });

  it("falls back to bars for a line over a dimension that is not ordered", () => {
    render({ id: "linea", type: "line", view: "productos" });
    expect(rects().length).toBeGreaterThan(0);
    expect(container.querySelectorAll("path")).toHaveLength(0);
    expect(container.querySelector("svg[role='img']")?.getAttribute("aria-label")).toBe(productos.summary);
  });
});

describe("pie and donut", () => {
  const top = { id: "tarta", type: "pie" as const, view: "productos", top_n: 3 };

  it("keeps the top_n slices and groups the rest under the localised label", () => {
    render(top);
    const rows = Array.from(container.querySelectorAll("li")).map((row) => row.textContent ?? "");

    expect(container.querySelectorAll("path")).toHaveLength(4);
    expect(rows).toHaveLength(4);
    expect(rows[3]).toContain(t.layout.others);
    expect(rows[3]).toContain("20,00");
    expect(rows[3]).toContain("20,0");
    expect(rows[0]).toContain("Alimento premium");
  });

  it("uses the layout's own label for the grouped slice", () => {
    render({ ...top, other_label: "resto" });
    const rows = Array.from(container.querySelectorAll("li")).map((row) => row.textContent ?? "");
    expect(rows[3]).toContain("resto");
  });

  it("draws a donut with an inner ring", () => {
    render({ ...top, id: "dona", type: "donut" });
    const paths = Array.from(container.querySelectorAll("path"));
    expect(paths).toHaveLength(4);
    for (const path of paths) expect(path.getAttribute("d")?.match(/A/g)).toHaveLength(2);
  });
});

describe("KPI sparkline", () => {
  it("draws the metric's own series when the layout asks for it", () => {
    render({ id: "mes", type: "kpi", view: "resumen", metric: "net_sales", sparkline: true });
    const sparkline = container.querySelector("svg[viewBox='0 0 96 24']");
    expect(sparkline).not.toBeNull();
    expect(sparkline?.querySelector("path")).not.toBeNull();
  });

  it("draws no sparkline when the layout does not ask for one", () => {
    render({ id: "mes", type: "kpi", view: "resumen" });
    expect(container.querySelector("svg[viewBox='0 0 96 24']")).toBeNull();
  });
});

describe("table component attributes", () => {
  it("orders and subsets the emitted columns, sorts, pages and prints the engine's totals", () => {
    container = mount(
      <LayoutRenderer
          layout={{
            components: [
              {
                id: "detalle",
                type: "table",
                view: "marcas",
                columns: ["net_sales", "product"],
                sort: { by: "net_sales", dir: "desc" },
                page_size: 5,
                totals: true,
              },
            ],
          }}
          data={{
            ...data,
            views: data.views.map((view) =>
              view.id === "marcas" ? { ...view, totals: { net_sales: 30, orders: 6 } } : view,
            ),
          }}
        def={def}
      />,
    );

    const headers = Array.from(container.querySelectorAll("th")).map((cell) => cell.textContent);
    expect(headers).toEqual(["Ventas netas", "Producto"]);
    // Sorted desc: the 20,00 row comes before the 10,00 one.
    const firstRow = container.querySelector("tbody tr")?.textContent ?? "";
    expect(firstRow.indexOf("20,00")).toBeLessThan(firstRow.indexOf("Vacuna triple"));
    // The totals row prints the engine's figure, not the sum of the visible columns' cells.
    expect(container.querySelector("tfoot")?.textContent).toContain("30,00");
    expect(container.querySelector("tfoot")?.textContent).toContain(t.layout.totals);
  });
});
