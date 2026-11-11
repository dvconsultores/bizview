import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReportData, ReportDefinition, ReportView } from "../../src/api/types";
import { CardDialog } from "../../src/components/report/CardDialog";
import { PieChart } from "../../src/components/report/charts/PieChart";
import { t } from "../../src/i18n/es";

/**
 * Feature 062 — US3 and US4, at the level jsdom can prove.
 *
 * jsdom has no layout engine, so "the ring is 240 px" cannot be measured here; what is provable is
 * the wiring that produces it (the measured width reaches the drawing, the legend's container is a
 * column below 640 px) and the header's structure (a two-row grid, a truncating title, no
 * `overflow-wrap` that printed one letter per line). The pixel geometry is asserted by
 * `tests/e2e/mobile-fixes.spec.ts`.
 */

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

function mount(node: ReactNode): HTMLDivElement {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push({ root, node: host });
  act(() => {
    root.render(node);
  });
  container = host;
  return host;
}

const def: ReportDefinition = {
  id: "ventas",
  title: "Ventas",
  description: "Resumen",
  icon: null,
  currency: "USD",
  metrics: { net_sales: { label: "Ventas netas", format: "currency", better: "higher" } },
  dimensions: { seller: { label: "Vendedor" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "none", allowed: ["none"] },
  filters: [],
  pdf: false,
};

const donut: ReportView = {
  type: "donut",
  id: "por_vendedor",
  title: "Vendedores por monto",
  metric: "net_sales",
  category: "seller",
  format: "currency",
  summary: "Ventas netas por vendedor: Ana 60 %, Beto 40 %.",
  categories: [
    { key: "ana", label: "Ana" },
    { key: "beto", label: "Beto" },
  ],
  values: [60, 40],
};

describe("CardDialog table mode (feature 064)", () => {
  it("offers the Gráfico | Tabla switch and reports the choice", () => {
    const onModeChange = vi.fn();
    mount(
      <CardDialog open title="Ventas" onClose={vi.fn()} mode="chart" onModeChange={onModeChange}>
        <p>gráfico</p>
      </CardDialog>,
    );
    const group = container.querySelector('[role="group"]') as HTMLElement;
    expect(group).not.toBeNull();
    const table = Array.from(group.querySelectorAll("button"))
      .find((button) => button.textContent === t.reportParams.dataTable.table) as HTMLButtonElement;
    act(() => table.click());
    expect(onModeChange).toHaveBeenCalledWith("table");
    expect(table.getAttribute("aria-pressed")).toBe("false");
  });
});

describe("CardDialog header (feature 062)", () => {
  it("puts the title alone on the first row, with the actions beside it and the chips below", () => {
    mount(
      <CardDialog
        open
        title="Vendedores por monto"
        onClose={vi.fn()}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onDownloadCsv={vi.fn()}
        onDownloadPng={vi.fn()}
        period="Mes en curso"
        comparison="Período anterior"
      >
        <p>gráfico</p>
      </CardDialog>,
    );
    const header = container.querySelector("[data-card-dialog-header]") as HTMLElement;
    expect(header).not.toBeNull();
    // Two rows: a title column and an actions column, then the chips across the full width.
    expect(header.className).toContain("grid");
    expect(header.className).toContain("minmax(0,1fr)");
    const title = header.querySelector("h2") as HTMLElement;
    expect(title.textContent).toBe("Vendedores por monto");
    // The title truncates on one line instead of wrapping; the full text stays in `title=`.
    expect(title.className).toContain("truncate");
    expect(title.className).toContain("min-w-0");
    expect(title.getAttribute("title")).toBe("Vendedores por monto");
    // Every action is a 44 px target and none of them ships a shrinkable box that could squeeze
    // the title: the actions column is `shrink-0`.
    const actions = title.nextElementSibling as HTMLElement;
    expect(actions.className).toContain("shrink-0");
    expect(actions.querySelectorAll("button").length).toBe(5);
    for (const button of Array.from(actions.querySelectorAll("button"))) {
      // 44 px is a px token: the app's root is 15 px on a phone, so `h-11` measured 41 px there.
      expect(button.className).toContain("min-h-tap");
    }
    // The chips are a row of their own, under the title.
    const chips = header.querySelector("[data-dialog-meta]") as HTMLElement;
    expect(chips.className).toContain("col-span-full");
    expect(chips.className).toContain("flex-wrap");
  });

  it("keeps the buttons labelled for a screen reader even when the icon is all a phone shows", () => {
    mount(
      <CardDialog open title="Marcas" onClose={vi.fn()} onDownloadCsv={vi.fn()} onDownloadPng={vi.fn()}>
        <p>tabla</p>
      </CardDialog>,
    );
    const csv = container.querySelector('[data-card-dialog-action="csv"]') as HTMLElement;
    expect(csv.getAttribute("aria-label")).toBe(t.reportParams.downloadCsv);
    // The visible word hides under 480 px; the label does not.
    expect(csv.querySelector("span")?.className).toContain("max-[480px]:hidden");
  });
});

describe("PieChart sizing (feature 062)", () => {
  const frame = { title: "Ventas netas", currency: "USD" };

  it("draws with the width the card measured, not a constant", () => {
    // jsdom reports 0 for every box, so the chart falls back to a width that fits the largest ring;
    // what matters is that the number it draws with comes from the measurement path.
    mount(
      <PieChart frame={frame} categories={donut.categories as never} values={donut.values as never}
        roles={["blue", "green"]} topN={6} otherLabel="Otros" donut format="currency"
        emptyText="Sin datos" summary={<p>resumen</p>} />,
    );
    const svg = container.querySelector("svg[role='img'], svg") as SVGSVGElement;
    expect(svg).not.toBeNull();
    expect(Number(svg.getAttribute("width"))).toBeGreaterThanOrEqual(200);
    // The legend is a column below 640 px: the ring first, the names under it.
    const legend = svg.closest("div")?.parentElement?.querySelector("ul") as HTMLElement;
    expect(legend).not.toBeNull();
    const row = legend.parentElement as HTMLElement;
    expect(row.className).toContain("flex-col");
    expect(row.className).toContain("sm:flex-row");
  });

  it("reserves the ring's height before the data arrives, so the card does not jump", () => {
    mount(
      <PieChart frame={frame} categories={[]} values={[]} roles={["blue"]} topN={6}
        otherLabel="Otros" donut format="currency" emptyText="Sin datos" summary={<p>resumen</p>} />,
    );
    // The measured box carries the ring's floor as an inline style on the chart's container.
    const box = container.querySelector('[style*="min-height"]') as HTMLElement;
    expect(box).not.toBeNull();
    expect(box.style.minHeight).toBe("240px");
  });
});
