import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  LayoutProblem,
  ReportData,
  ReportDefinition,
  ReportView,
  WebComponent,
  WebLayout,
} from "../../src/api/types";
import { LayoutRenderer } from "../../src/components/report/LayoutRenderer";
import { ReportViews } from "../../src/components/report/ReportViews";
import { t } from "../../src/i18n/es";

// Feature 026 — US1: a declared layout.web composes the dashboard (specs/026-declarative-layouts).

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// jsdom has no ResizeObserver; the charts measure their container with one.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

function render(node: React.ReactNode) {
  act(() => {
    root.render(node);
  });
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
  periods: { default: "mtd", allowed: ["mtd", "custom"] },
  compare: { default: "previous_period", allowed: ["none", "previous_period"] },
  filters: ["product"],
  pdf: true,
  ai_narrative: false,
};

const kpis: ReportView = {
  type: "kpis",
  id: "resumen",
  summary: "Ventas netas de 100,00 USD y 4 pedidos en el período.",
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

const daily: ReportView = {
  type: "trend",
  id: "diaria",
  metric: "net_sales",
  label: "Ventas netas",
  format: "currency",
  grain: "day",
  summary: "Ventas netas por día: máximo 30,00 USD el 3 de septiembre.",
  points: [
    { bucket: "2026-09-01", value: 10 },
    { bucket: "2026-09-02", value: null },
    { bucket: "2026-09-03", value: 30 },
  ],
};

const weekly: ReportView = {
  type: "trend",
  id: "pedidos-semana",
  metric: "orders",
  label: "Pedidos",
  format: "integer",
  grain: "week",
  summary: "Pedidos por semana: máximo 9 el 2 de septiembre.",
  points: [
    { bucket: "2026-08-31", value: 3 },
    { bucket: "2026-09-07", value: 9 },
  ],
};

const byProduct: ReportView = {
  type: "ranking",
  id: "productos",
  metric: "net_sales",
  dimension: "product",
  title: "Ventas por producto",
  label: "Ventas netas",
  dimension_label: "Producto",
  format: "currency",
  summary: "Ventas netas por producto: Alimento premium encabeza con 40,00 USD.",
  items: [
    { key: "Alimento premium", value: 40, share: 40, previous: 30, change: { pct: 33, new: false } },
    { key: "Vacuna triple", value: 60, share: 60, previous: 50, change: { pct: 20, new: false } },
  ],
};

const detail: ReportView = {
  type: "table",
  id: "detalle",
  title: "Detalle por día",
  summary: "Detalle por día de las ventas netas del período.",
  columns: [
    { id: "day", label: "Día", kind: "dimension" },
    { id: "net", label: "Ventas netas", kind: "metric", format: "currency" },
  ],
  rows: [
    { day: "2026-09-01", net: 10 },
    { day: "2026-09-02", net: null },
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
  views: [kpis, daily, weekly, byProduct, detail],
};

const cells = () => Array.from(container.querySelectorAll<HTMLElement>("[data-layout-id]"));
const grid = () => container.querySelector<HTMLElement>("[data-testid='layout-grid']");

function component(partial: Partial<WebComponent> & Pick<WebComponent, "id" | "type">): WebComponent {
  return partial;
}

describe("LayoutRenderer grid", () => {
  const layout: WebLayout = {
    gutter: "md",
    components: [
      component({ id: "mes", type: "kpi", view: "resumen", span: 12 }),
      component({ id: "diaria", type: "line", view: "diaria", span: 8 }),
      component({ id: "productos", type: "bar", view: "productos", span: 4 }),
    ],
  };

  it("is one column on phones and twelve from the md breakpoint", () => {
    render(<LayoutRenderer layout={layout} data={data} def={def} />);
    const classes = grid()!.className;
    expect(classes).toContain("grid-cols-1");
    expect(classes).toContain("md:grid-cols-12");
  });

  it("keeps the declared order as the DOM order and honours span", () => {
    render(<LayoutRenderer layout={layout} data={data} def={def} />);
    expect(cells().map((cell) => cell.dataset.layoutId)).toEqual(["mes", "diaria", "productos"]);
    expect(cells()[0].className).toContain("md:col-span-12");
    expect(cells()[1].className).toContain("md:col-span-8");
    expect(cells()[2].className).toContain("md:col-span-4");
  });

  it("defaults to a full-width cell when span is absent", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "nota", type: "text", text: "Cifras provisionales." })] }}
        data={data}
        def={def}
      />,
    );
    expect(cells()[0].className).toContain("md:col-span-12");
    expect(container.textContent).toContain("Cifras provisionales.");
  });

  it("renders nothing at all for an empty component list", () => {
    render(<LayoutRenderer layout={{ components: [] }} data={data} def={def} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("LayoutRenderer binding", () => {
  it("resolves each component against the payload view with that id, never by type", () => {
    render(
      <LayoutRenderer
        layout={{
          components: [
            component({ id: "diaria", type: "line", view: "diaria" }),
            component({ id: "semanal", type: "line", view: "pedidos-semana" }),
          ],
        }}
        data={data}
        def={def}
      />,
    );
    const labels = Array.from(container.querySelectorAll("svg[role='img']")).map((svg) =>
      svg.getAttribute("aria-label"),
    );
    expect(labels).toEqual([daily.summary, weekly.summary]);
  });

  it("renders the error card for an unknown type, naming the id and the type", () => {
    render(
      <LayoutRenderer
        layout={{ components: [{ ...component({ id: "raro", type: "map" as WebComponent["type"] }) }] }}
        data={data}
        def={def}
      />,
    );
    expect(container.textContent).toContain(t.layout.errorCard("raro", "map"));
  });

  it("renders the error card for one missing view and keeps the rest of the dashboard", () => {
    render(
      <LayoutRenderer
        layout={{
          components: [
            component({ id: "mes", type: "kpi", view: "resumen" }),
            component({ id: "roto", type: "table", view: "no-existe" }),
          ],
        }}
        data={data}
        def={def}
      />,
    );
    expect(container.textContent).toContain(t.layout.missingView("roto", "no-existe"));
    // The component next to it still renders its figure.
    expect(container.textContent).toContain("100,00");
    expect(cells().map((cell) => cell.dataset.layoutId)).toEqual(["mes", "roto"]);
  });

  it("renders the error card when a declared metric is not in the bound view", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "mes", type: "kpi", view: "resumen", metric: "margen" })] }}
        data={data}
        def={def}
      />,
    );
    expect(container.textContent).toContain(t.layout.missingMetric("mes", "margen"));
  });

  it("renders the error card when the bound view cannot serve the component", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "raro", type: "kpi", view: "detalle" })] }}
        data={data}
        def={def}
      />,
    );
    expect(container.textContent).toContain(t.layout.viewShape("raro", "detalle"));
  });
});

describe("LayoutRenderer accessibility summary", () => {
  it("labels the chart with the payload summary and shows it as a caption by default", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "diaria", type: "line", view: "diaria" })] }}
        data={data}
        def={def}
      />,
    );
    const svg = container.querySelector("svg[role='img']");
    expect(svg?.getAttribute("aria-label")).toBe(daily.summary);
    expect(container.querySelector("figcaption")?.textContent).toBe(daily.summary);
  });

  it("omits the label and the caption when summary is false", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "diaria", type: "line", view: "diaria", summary: false })] }}
        data={data}
        def={def}
      />,
    );
    expect(container.querySelector("svg[role='img']")).toBeNull();
    expect(container.querySelector("figcaption")).toBeNull();
  });

  it("shows validation warnings as a quiet note, not as an error state", () => {
    const problems: LayoutProblem[] = [
      {
        level: "warning",
        code: "layout_chart_unsuitable",
        path: "/layout/web/components/1/x",
        message: "La línea se dibuja como barras: el eje no es una dimensión ordenada.",
      },
    ];
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "diaria", type: "line", view: "diaria" })] }}
        data={data}
        def={def}
        problems={problems}
      />,
    );
    expect(container.textContent).toContain(t.layout.problemsTitle);
    expect(container.textContent).toContain("el eje no es una dimensión ordenada");
    expect(container.querySelector("[role='alert']")).toBeNull();
  });
});

describe("text, filters and spacer blocks", () => {
  it("renders the markdown subset as elements, never as HTML", () => {
    render(
      <LayoutRenderer
        layout={{
          components: [
            component({
              id: "nota",
              type: "text",
              text: "Cifras **provisionales** del _cierre_.\n[Ver detalle](https://example.com)\n<script>alert(1)</script>",
            }),
          ],
        }}
        data={data}
        def={def}
      />,
    );
    expect(container.querySelector("strong")?.textContent).toBe("provisionales");
    expect(container.querySelector("em")?.textContent).toBe("cierre");
    expect(container.querySelector("a")?.getAttribute("href")).toBe("https://example.com");
    expect(container.querySelector("a")?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(container.querySelectorAll("br")).toHaveLength(2);
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
  });

  it("ignores a link whose scheme is not safe", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "nota", type: "text", text: "[Peligro](javascript:alert(1))" })] }}
        data={data}
        def={def}
      />,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("Peligro");
  });

  it("reuses the report's own filter controls, restricted by only[]", () => {
    const withFilters: ReportDefinition = {
      ...def,
      filters: ["product", "store"],
      dimensions: { product: { label: "Producto" }, store: { label: "Tienda" } },
    };
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "filtros", type: "filters", only: ["product"] })] }}
        data={data}
        def={withFilters}
        params={{
          applied: { period: "mtd", from: "", to: "", compare: "previous_period", filters: {} },
          onApply: () => undefined,
          loadOptions: async () => ({ items: [], truncated: false }),
        }}
      />,
    );
    expect(container.querySelector("[data-testid='params-form']")).not.toBeNull();
    expect(container.textContent).toContain("Producto");
    expect(container.textContent).not.toContain("Tienda");
  });

  it("applies a filter change through the report screen's own wiring", () => {
    const onApply = vi.fn();
    const applied = { period: "mtd" as const, from: "", to: "", compare: "previous_period" as const, filters: {} };
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "filtros", type: "filters" })] }}
        data={data}
        def={{ ...def, periods: { default: "mtd", allowed: ["mtd", "last_month"] } }}
        params={{ applied, onApply, loadOptions: async () => ({ items: [], truncated: false }) }}
      />,
    );

    const period = container.querySelector<HTMLSelectElement>("select");
    expect(period).not.toBeNull();
    act(() => {
      period!.value = "last_month";
      period!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const submit = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.trim() === t.reportParams.apply,
    );
    expect(submit).not.toBeUndefined();
    act(() => {
      submit!.click();
    });

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0]).toEqual({ ...applied, period: "last_month" });
  });

  it("shows the applied filters instead of dead controls when it has no wiring", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "filtros", type: "filters" })] }}
        data={{ ...data, filters: { product: ["Vacuna triple"] } }}
        def={def}
      />,
    );
    expect(container.textContent).toContain("Vacuna triple");
    expect(container.querySelector("[data-testid='params-form']")).toBeNull();
  });

  it("renders a spacer as an empty cell", () => {
    render(
      <LayoutRenderer
        layout={{ components: [component({ id: "aire", type: "spacer", size: "lg", span: 6 })] }}
        data={data}
        def={def}
      />,
    );
    const cell = cells()[0].firstElementChild;
    expect(cell?.getAttribute("aria-hidden")).toBe("true");
    expect(cell?.className).toContain("h-3");
    expect(cell?.className).toContain("md:h-10");
  });
});

describe("ReportViews", () => {
  it("renders data.views in payload order when there is no layout.web", () => {
    render(<ReportViews data={data} def={def} />);
    const html = container.innerHTML;
    expect(html).toContain(t.reportParams.display.trend("Ventas netas"));
    expect(html.indexOf(t.reportParams.display.indicators)).toBeLessThan(
      html.indexOf(t.reportParams.display.trend("Ventas netas")),
    );
  });

  it("delegates to the renderer when the definition declares layout.web", () => {
    render(
      <ReportViews
        data={data}
        def={{
          ...def,
          layout: { web: { components: [component({ id: "nota", type: "text", text: "Composición declarada." })] } },
        }}
      />,
    );
    expect(grid()).not.toBeNull();
    expect(container.textContent).toContain("Composición declarada.");
    expect(container.textContent).not.toContain(t.reportParams.display.indicators);
  });
});
