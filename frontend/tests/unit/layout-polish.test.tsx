import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReportData, ReportDefinition, ReportView, WebComponent } from "../../src/api/types";
import { CardDialog } from "../../src/components/report/CardDialog";
import { LayoutRenderer } from "../../src/components/report/LayoutRenderer";
import axe from "axe-core";
import { fitLabel, labelColumn, measureText } from "../../src/lib/chartLabel";
import { ReportViews } from "../../src/components/report/ReportViews";
import { RankingTable } from "../../src/components/report/RankingTable";

/** Feature 056: a KPI fills its span, cards in a row share a height, labels fit, values appear on
 * hover, and a card opens full screen. jsdom has no layout engine, so the pixel outcomes are proved
 * by the structure that causes them (one card, `h-full` chain, minimum heights, measured labels). */

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
    await act(async () => { entry.root.unmount(); });
    entry.node.remove();
  }
});

function mount(node: ReactNode): HTMLDivElement {
  const node_ = document.createElement("div");
  document.body.appendChild(node_);
  const root = createRoot(node_);
  mounted.push({ root, node: node_ });
  act(() => { root.render(node); });
  container = node_;
  return node_;
}

const def: ReportDefinition = {
  id: "ventas",
  title: "Ventas",
  description: "Resumen",
  icon: null,
  currency: "USD",
  metrics: { net_sales: { label: "Ventas netas", format: "currency", better: "higher" } },
  dimensions: { product: { label: "Producto" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "previous_period", allowed: ["none", "previous_period"] },
  filters: ["product"],
  pdf: true,
  ai_narrative: false,
};

const kpis: ReportView = {
  type: "kpis",
  id: "resumen",
  items: [
    { metric: "net_sales", label: "Ventas netas", format: "currency", better: "higher",
      value: 149250.44, previous: 36800, change: { pct: 302.8, new: false } },
    { metric: "orders", label: "Pedidos", format: "integer", better: "higher",
      value: 120, previous: 100, change: { pct: 20, new: false } },
  ],
};

const LONG = "BIOLOGICOS PROVIACOL FORTE SUSPENSION 250 ML";

const products: ReportView = {
  type: "table",
  id: "marcas",
  title: "Marcas",
  summary: "Ventas por marca.",
  columns: [
    { id: "product", label: "Producto", kind: "dimension" },
    { id: "net_sales", label: "Ventas netas", kind: "metric", format: "currency" },
  ],
  rows: [
    { product: LONG, net_sales: 50 },
    { product: "Antibiótico", net_sales: 25 },
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
  views: [kpis, products],
};

function render(components: WebComponent[], extra: Record<string, unknown> = {},
                source: ReportData = data) {
  return mount(
    <LayoutRenderer layout={{ components }} data={source} def={def} {...extra} />,
  );
}

describe("a KPI fills its span", () => {
  it("renders one card, with no inner grid, as wide as its cell", () => {
    render([{ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales", span: 6 }]);
    // The wrapper the old implementation drew is what took a quarter of the span.
    expect(container.querySelector("ul")).toBeNull();
    const cards = container.querySelectorAll("[data-kpi-card]");
    expect(cards).toHaveLength(1);
    expect(cards[0].className).toContain("w-full");
    expect(cards[0].className).toContain("h-full");
    const cell = container.querySelector("[data-layout-id='ventas']") as HTMLElement;
    expect(cell.style.minHeight).toBe("150px");
    expect(cell.className).toContain("h-full");
  });

  it("keeps the grid when the kpis view has no layout component", () => {
    render([{ id: "todos", type: "kpi", view: "resumen", span: 12 }]);
    render([{ id: "ventas", type: "kpi", view: "resumen", span: 6 }]);
    // Without a metric the component shows every item, still as one card each, never a grid.
    expect(container.querySelector("ul")).toBeNull();
  });

  it("gives the delta row its own space, with and without a comparison", () => {
    render([{ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales", span: 6 }]);
    let row = container.querySelector("[data-kpi-delta-row]") as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.className).toContain("pt-3");
    expect(row.style.minHeight).not.toBe("");
    expect(row.textContent).toContain("+302,8");

    render([{ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales", span: 6,
              delta: "none" }]);
    row = container.querySelector("[data-kpi-delta-row]") as HTMLElement;
    expect(row.style.minHeight).not.toBe("");
  });
});

describe("cards in a row share a height", () => {
  it("gives every chart cell a minimum height and stretches its card", () => {
    render([
      { id: "barras", type: "bar", view: "marcas", x: "product", series: ["net_sales"] },
      { id: "torta", type: "pie", view: "marcas", category: "product", value: "net_sales" },
    ]);
    const cells = Array.from(container.querySelectorAll("[data-layout-id]")) as HTMLElement[];
    expect(cells.map((cell) => cell.style.minHeight)).toEqual(["320px", "320px"]);
    const cards = Array.from(container.querySelectorAll("[data-layout-id] > div")) as HTMLElement[];
    expect(cards.every((card) => card.className.includes("h-full"))).toBe(true);
  });
});

describe("category labels fit", () => {
  it("shortens with a trailing ellipsis, never at the left", () => {
    const shortened = fitLabel(LONG, 90);
    expect(shortened.endsWith("…")).toBe(true);
    expect(LONG.startsWith(shortened.slice(0, 4))).toBe(true);
    expect(measureText(shortened)).toBeLessThanOrEqual(measureText(LONG));
  });

  it("measures the column within the documented bounds", () => {
    expect(labelColumn(1000, [LONG])).toBeGreaterThanOrEqual(96);
    expect(labelColumn(1000, [LONG])).toBeLessThanOrEqual(220);
    expect(labelColumn(160, [LONG])).toBeLessThanOrEqual(120);
  });

  it("puts the full label over its bar on a phone, and carries the name in a title", () => {
    // jsdom measures the chart at its 320 px fallback: the phone layout is what renders.
    render([{ id: "ancho", type: "bar", view: "marcas", x: "product", series: ["net_sales"],
              orientation: "horizontal" }]);
    const texts = Array.from(container.querySelectorAll("svg text")).map((node) => node.textContent ?? "");
    expect(texts).toContain(LONG);
    const titles = Array.from(container.querySelectorAll("title")).map((node) => node.textContent ?? "");
    expect(titles.some((title) => title.startsWith(LONG))).toBe(true);
  });
});

describe("values on hover and by declaration", () => {
  it("shows a chip with the name, the value and the share, and dims the rest", () => {
    render([{ id: "barras", type: "bar", view: "marcas", x: "product", series: ["net_sales"] }]);
    const rects = Array.from(container.querySelectorAll("rect"));
    expect(rects.length).toBeGreaterThan(1);
    // React derives `onPointerEnter` from `pointerover`, so that is the event a browser sends.
    act(() => { rects[0].dispatchEvent(new PointerEvent("pointerover", { bubbles: true })); });
    const chip = container.querySelector("[data-value-chip]");
    expect(chip).not.toBeNull();
    expect(chip!.textContent).toContain("BIOLOGICOS");
    expect(chip!.textContent).toContain("50,00");
    expect(chip!.textContent).toContain("%");
    // The other bar dims so the eye stays on the hovered one.
    expect(rects[1].getAttribute("opacity")).toBe("0.7");
  });

  it("prints the value when the component declares labels", () => {
    render([{ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales", span: 6 }]);
    render([{ id: "barras", type: "bar", view: "marcas", x: "product", series: ["net_sales"],
              labels: true }]);
    const values = Array.from(container.querySelectorAll("svg text"))
      .map((node) => node.textContent ?? "")
      .filter((text) => text.includes("50"));
    expect(values.length).toBeGreaterThan(0);
  });
});

describe("maximize", () => {
  it("offers Ampliar on a card and reports the component id", () => {
    const onMaximize = vi.fn();
    render([{ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales", span: 6 }],
           { onMaximize });
    const button = container.querySelector("[data-maximize='ventas']") as HTMLButtonElement;
    expect(button).not.toBeNull();
    expect(button.getAttribute("aria-label")).toContain("Ampliar");
    act(() => { button.click(); });
    expect(onMaximize).toHaveBeenCalledWith("ventas");
  });

  it("does not offer it on text, filters or spacers", () => {
    render([{ id: "nota", type: "text", text: "hola", span: 12 }], { onMaximize: vi.fn() });
    expect(container.querySelector("[data-maximize]")).toBeNull();
  });
});

describe("the full-screen card", () => {
  const props = () => ({
    open: true,
    title: "Ventas netas",
    onClose: vi.fn(),
    onPrevious: vi.fn(),
    onNext: vi.fn(),
    onDownloadPng: vi.fn(),
    children: <p>gráfico</p>,
  });

  it("is a labelled dialog that closes with Escape", () => {
    const p = props();
    mount(<CardDialog {...p} />);
    const dialog = container.querySelector("[role='dialog']") as HTMLElement;
    expect(dialog).not.toBeNull();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(p.onClose).toHaveBeenCalled();
  });

  it("offers the view's CSV when the card has one", () => {
    const onDownloadCsv = vi.fn();
    mount(<CardDialog open title="Marcas" onClose={vi.fn()} onDownloadCsv={onDownloadCsv}>
      <p>tabla</p>
    </CardDialog>);
    const csv = Array.from(container.querySelectorAll("button"))
      .find((button) => (button.textContent ?? "").includes("CSV")) as HTMLButtonElement;
    expect(csv).toBeTruthy();
    act(() => { csv.click(); });
    expect(onDownloadCsv).toHaveBeenCalled();
  });

  it("moves to the next and previous card with the arrow keys", () => {
    const p = props();
    mount(<CardDialog {...p} />);
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    });
    expect(p.onNext).toHaveBeenCalled();
    expect(p.onPrevious).toHaveBeenCalled();
  });
});

describe("the menu offers the same action", () => {
  it("has Ampliar inside a ranking card's menu", () => {
    const onMaximize = vi.fn();
    const ranking: ReportView = {
      type: "ranking", id: "top", metric: "net_sales", dimension: "product",
      title: "Top", label: "Ventas netas", dimension_label: "Producto", format: "currency",
      summary: "Top de ventas.", items: [{ key: "A", value: 10, share: 100, previous: null, change: null }],
    };
    mount(<RankingTable view={ranking} currency="USD" compared={false} better="higher"
                        onMaximize={onMaximize} />);
    const trigger = container.querySelector("button[aria-expanded]") as HTMLButtonElement;
    act(() => { trigger.click(); });
    const item = Array.from(container.querySelectorAll("button"))
      .find((button) => (button.textContent ?? "").includes("Ampliar")) as HTMLButtonElement;
    expect(item).toBeTruthy();
    act(() => { item.click(); });
    expect(onMaximize).toHaveBeenCalled();
  });
});

describe("default view cards", () => {
  it("offer Ampliar with a stable id when there is no layout", () => {
    const onMaximize = vi.fn();
    mount(<ReportViews data={data} def={def} onMaximize={onMaximize} />);
    const button = container.querySelector("[data-maximize='view-0']") as HTMLButtonElement;
    expect(button).not.toBeNull();
    act(() => { button.click(); });
    expect(onMaximize).toHaveBeenCalledWith("view-0");
  });
});

describe("a line point", () => {
  it("shows its value in a chip on hover", () => {
    const trend: ReportView = {
      type: "trend", id: "diaria", metric: "net_sales", label: "Ventas netas", format: "currency",
      grain: "day", summary: "Ventas por día.",
      points: [
        { bucket: "2026-09-01", value: 10, previous: 5 },
        { bucket: "2026-09-02", value: 30, previous: 12 },
      ],
    };
    mount(<LayoutRenderer layout={{ components: [{ id: "linea", type: "line", view: "diaria" }] }}
                          data={{ ...data, views: [trend] }} def={def} />);
    const point = Array.from(container.querySelectorAll("svg circle"))
      .find((node) => node.getAttribute("fill") === "transparent") as SVGCircleElement;
    expect(point).toBeTruthy();
    act(() => { point.dispatchEvent(new PointerEvent("pointerover", { bubbles: true })); });
    const chip = container.querySelector("[data-value-chip]");
    expect(chip).not.toBeNull();
    expect(chip!.textContent).toContain("10,00");
  });
});

describe("the layout without a card open", () => {
  it("renders exactly as before when nothing is maximized", () => {
    render([{ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales", span: 6 }],
           { onMaximize: vi.fn() });
    expect(container.querySelector("[data-card-dialog]")).toBeNull();
  });
});

/** Feature 056b: the maximised card must fill the dialog, not keep its dashboard size. */
describe("the maximised card fills the dialog (056b)", () => {
  function mountDialog(component: WebComponent, options: { width?: number; height?: number } = {}) {
    // jsdom has no layout engine: the frame's measured size is stubbed so the fill chain is proved
    // end to end — the same numbers a 1440 × 900 dialog reports in a browser.
    const width = options.width ?? 1400;
    const height = options.height ?? 900;
    const proto = HTMLElement.prototype as unknown as {
      clientWidth: number; clientHeight: number;
    };
    const originalWidth = Object.getOwnPropertyDescriptor(proto, "clientWidth");
    const originalHeight = Object.getOwnPropertyDescriptor(proto, "clientHeight");
    Object.defineProperty(proto, "clientWidth", { configurable: true, get: () => width });
    Object.defineProperty(proto, "clientHeight", { configurable: true, get: () => height });
    const node = mount(
      <LayoutRenderer
        layout={{ components: [{ ...component, span: 12 }] }}
        data={data}
        def={def}
        fill
        maximized
      />,
    );
    return {
      node,
      restore: () => {
        if (originalWidth) Object.defineProperty(proto, "clientWidth", originalWidth);
        if (originalHeight) Object.defineProperty(proto, "clientHeight", originalHeight);
      },
    };
  }

  it("takes the whole grid and stretches the cell", () => {
    const { restore } = mountDialog({ id: "ancho", type: "bar", view: "marcas", x: "product",
                                      series: ["net_sales"], orientation: "horizontal" });
    try {
      const grid = container.querySelector("[data-testid='layout-grid']") as HTMLElement;
      expect(grid.className).toContain("h-full");
      const cell = container.querySelector("[data-layout-id='ancho']") as HTMLElement;
      expect(cell.className).toContain("h-full");
      // span 12 = the whole width, never half of it.
      expect(cell.getAttribute("data-layout-span")).toBe("12");
    } finally {
      restore();
    }
  });

  it("draws the chart at the dialog's size, with no ellipsis on a 45-character name", () => {
    const { restore } = mountDialog({ id: "ancho", type: "bar", view: "marcas", x: "product",
                                      series: ["net_sales"], orientation: "horizontal" });
    try {
      const svg = container.querySelector("svg") as SVGSVGElement;
      expect(Number(svg.getAttribute("width"))).toBe(1400);
      expect(Number(svg.getAttribute("height"))).toBe(900);
      const labels = Array.from(svg.querySelectorAll("text")).map((node) => node.textContent ?? "");
      expect(labels).toContain(LONG);
      expect(labels.some((label) => label.endsWith("…") && label.includes("BIOLOGICOS"))).toBe(false);
    } finally {
      restore();
    }
  });

  it("drops its own title, the Ampliar control and the menu", () => {
    const { restore } = mountDialog({ id: "ancho", type: "bar", view: "marcas", x: "product",
                                      series: ["net_sales"], orientation: "horizontal" });
    try {
      expect(container.querySelectorAll("h2")).toHaveLength(0);
      expect(container.querySelector("[data-maximize]")).toBeNull();
      expect(container.querySelector("button[aria-expanded]")).toBeNull();
      const card = container.querySelector("[data-maximized]") as HTMLElement;
      expect(card).not.toBeNull();
      expect(card.className).toContain("p-0");
    } finally {
      restore();
    }
  });

  it("sizes a donut ring for the dialog and enlarges the KPI value", () => {
    const { restore } = mountDialog({ id: "torta", type: "donut", view: "marcas",
                                      category: "product", value: "net_sales" });
    try {
      const ring = container.querySelector("svg") as SVGSVGElement;
      expect(Number(ring.getAttribute("width"))).toBeGreaterThan(400);
    } finally {
      restore();
    }

    const second = mountDialog({ id: "ventas", type: "kpi", view: "resumen", metric: "net_sales" });
    try {
      const value = container.querySelector("[data-kpi-value]") as HTMLElement;
      expect(value.style.fontSize).toBe("clamp(44px, 6vw, 96px)");
      expect(container.querySelector("[data-maximize]")).toBeNull();
    } finally {
      second.restore();
    }
  });

  it("gives a table card no heading and no menu inside the dialog", () => {
    const { restore } = mountDialog({ id: "tabla", type: "table", view: "marcas" });
    try {
      expect(container.querySelector("h2")).toBeNull();
      expect(container.querySelector("button[aria-expanded]")).toBeNull();
    } finally {
      restore();
    }
  });
});

describe("label policy in the dialog", () => {
  it("fits 45 characters at 1440 px without shortening them", () => {
    const column = labelColumn(1440, [LONG], { maximized: true });
    expect(column).toBeGreaterThanOrEqual(measureText(LONG));
    expect(fitLabel(LONG, column)).toBe(LONG);
    // The dashboard cap still applies outside the dialog.
    expect(fitLabel(LONG, labelColumn(1000, [LONG]))).not.toBe(LONG);
  });
});

describe("moving between cards", () => {
  it("replaces the history entry so Back closes the dialog", async () => {
    // Read from the source: the arrow handler must not push a second history entry.
    const source = await import("node:fs").then(({ readFileSync }) =>
      readFileSync("src/pages/ReportView.tsx", "utf8"));
    expect(source).toMatch(/const go = \(step: -1 \| 1\) => \{[\s\S]*?onMaximize\(target, true\);/);
  });
});

describe("the dialog's accessibility", () => {
  it("has no serious or critical axe violations with the card inside", async () => {
    mount(
      <CardDialog open title="Clientes por monto" period="Mes en curso"
                  comparison="Período anterior" filters={["estado: pagado"]} onClose={vi.fn()}>
        <p>gráfico</p>
      </CardDialog>,
    );
    const results = await axe.run(container, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      rules: { "color-contrast": { enabled: false } },
    });
    const serious = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );
    expect(serious.map((violation) => violation.id)).toEqual([]);
  });

  it("names the period, the comparison and the filters in its header", () => {
    mount(
      <CardDialog open title="Clientes por monto" period="Mes en curso"
                  comparison="Período anterior" filters={["estado: pagado"]} onClose={vi.fn()}>
        <p>gráfico</p>
      </CardDialog>,
    );
    const meta = container.querySelector("[data-dialog-meta]") as HTMLElement;
    expect(meta).not.toBeNull();
    expect(meta.textContent).toContain("Mes en curso");
    expect(meta.textContent).toContain("Período anterior");
    expect(meta.textContent).toContain("estado: pagado");
  });
});

describe("a slice and a point carry their value", () => {
  it("shows a chip on a slice with the name, the value and the share", () => {
    render([{ id: "torta", type: "pie", view: "marcas", category: "product", value: "net_sales" }]);
    const slice = container.querySelector("svg path") as SVGPathElement;
    expect(slice).not.toBeNull();
    act(() => { slice.dispatchEvent(new PointerEvent("pointerover", { bubbles: true })); });
    const chip = container.querySelector("[data-value-chip]");
    expect(chip).not.toBeNull();
    expect(chip!.textContent).toContain("BIOLOGICOS");
    expect(chip!.textContent).toContain("%");
  });

  it("prints a value at each mark when the trend declares labels", () => {
    const trend: ReportView = {
      type: "trend", id: "diaria", metric: "net_sales", label: "Ventas netas", format: "currency",
      grain: "day", summary: "Ventas por día.",
      points: [
        { bucket: "2026-09-01", value: 10, previous: 5 },
        { bucket: "2026-09-02", value: 30, previous: 12 },
        { bucket: "2026-09-03", value: 20, previous: 8 },
      ],
    };
    mount(<LayoutRenderer layout={{ components: [{ id: "linea", type: "line", view: "diaria",
                                                    labels: true }] }}
                          data={{ ...data, views: [trend] }} def={def} />);
    const texts = Array.from(container.querySelectorAll("svg text")).map((node) => node.textContent ?? "");
    expect(texts.filter((text) => text.includes("10,00")).length).toBeGreaterThan(0);
    expect(texts.filter((text) => text.includes("30,00")).length).toBeGreaterThan(0);
  });
});
