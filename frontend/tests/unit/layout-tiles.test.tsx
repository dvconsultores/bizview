import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { LayoutRenderer } from "../../src/components/report/LayoutRenderer";
import { formatValue, formatValueCompact } from "../../src/lib/numbers";
import type { ReportData, ReportDefinition, WebComponent } from "../../src/api/types";

// @ts-expect-error test flag
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// @ts-expect-error test stub
globalThis.ResizeObserver = ResizeObserverStub;

let container: HTMLDivElement;
let mounted: Root | null = null;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  if (mounted) {
    act(() => mounted!.unmount());
    mounted = null;
  }
  container.remove();
});

function mount(element: JSX.Element) {
  mounted = createRoot(container);
  act(() => mounted!.render(element));
}

function render(component: WebComponent) {
  mount(<LayoutRenderer layout={{ components: [component] }} data={source} def={def} />);
}

const def: ReportDefinition = {
  id: "tiles-test",
  title: "Tiles",
  metrics: {
    fear_greed: { label: "Miedo y codicia", format: "number", better: "higher" },
    btc_dominance: { label: "Dominancia BTC", format: "percent", better: "higher" },
    eth_dominance: { label: "Dominancia ETH", format: "percent", better: "higher" },
  },
  dimensions: { symbol: { label: "Símbolo" } },
  filters: ["symbol"],
} as unknown as ReportDefinition;

const indicadores = {
  id: "indicadores",
  type: "kpis",
  title: "Indicadores",
  items: [
    {
      metric: "fear_greed",
      label: "Miedo y codicia",
      value: 61,
      previous: 55,
      change: { pct: 10.9 },
      better: "higher",
      format: "number",
    },
    {
      metric: "btc_dominance",
      label: "Dominancia BTC",
      value: 60.8,
      previous: 60.1,
      change: { pct: 1.2 },
      better: "higher",
      format: "percent",
    },
    {
      metric: "eth_dominance",
      label: "Dominancia ETH",
      value: 10.6,
      previous: 10.9,
      change: { pct: -2.8 },
      better: "higher",
      format: "percent",
    },
  ],
};

const activos = {
  id: "activos",
  type: "table",
  title: "Activos",
  columns: [
    { id: "logo_url", label: "Logo", kind: "dimension" },
    { id: "symbol", label: "Símbolo", kind: "dimension" },
    { id: "name", label: "Nombre", kind: "dimension" },
    { id: "price_usd", label: "Precio", kind: "metric", format: "currency" },
    { id: "pct24", label: "Var 24h", kind: "metric", format: "percent" },
  ],
  rows: Array.from({ length: 10 }, (_, i) => ({
    logo_url: "https://img.example/x.png",
    symbol: `C${i}`,
    name: `Coin ${i}`,
    price_usd: 1000 + i,
    pct24: i % 2 === 0 ? 2.5 : -3.1,
  })),
};

const source: ReportData = {
  selection: {
    period: "mtd",
    current: { from: "2026-09-01", to: "2026-09-30" },
    compare: "none",
    previous: null,
    partial: false,
    grain: "day",
  },
  filters: {},
  freshness: { updated_at: null, data_version: "v1" },
  views: [indicadores, activos],
} as unknown as ReportData;

describe("042 tiles", () => {
  it("gauge renders bands, needle and an accessible label", () => {
    render({ id: "g", type: "gauge", view: "indicadores", metric: "fear_greed" } as WebComponent);
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBe(5);
    expect(container.querySelectorAll("line").length).toBeGreaterThanOrEqual(1);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("role")).toBe("img");
    const aria = svg!.getAttribute("aria-label") ?? "";
    expect(aria).toContain("Miedo y codicia");
    expect(aria).toContain("61");
  });

  it("gauge on a table view renders an error card", () => {
    render({ id: "g2", type: "gauge", view: "activos", metric: "fear_greed" } as WebComponent);
    expect(container.textContent ?? "").toContain("g2");
  });

  it("share renders segments and remainder", () => {
    render({
      id: "s",
      type: "share",
      view: "indicadores",
      items: ["btc_dominance", "eth_dominance"],
      remainder_label: "Otros",
    } as WebComponent);
    const text = container.textContent ?? "";
    expect(text).toContain("Otros");
    expect(text).toContain("60,8");

    const bar = container.querySelector(".flex.h-3");
    expect(bar).not.toBeNull();
    const children = Array.from(bar!.children) as HTMLElement[];
    expect(children.length).toBe(3);
    for (const child of children) {
      expect(child.style.width).toContain("%");
    }
  });

  it("index renders labels, value and marker position", () => {
    render({
      id: "i",
      type: "index",
      view: "indicadores",
      metric: "fear_greed",
      low_label: "Bitcoin season",
      high_label: "Altcoin season",
    } as WebComponent);
    const text = container.textContent ?? "";
    expect(text).toContain("Bitcoin season");
    expect(text).toContain("Altcoin season");
    expect(text).toContain("61");

    const marker = container.querySelector(".absolute.h-5") as HTMLElement | null;
    expect(marker).not.toBeNull();
    expect(marker!.style.left).toBe("61%");
  });

  it("asset renders rows with default limit and honors explicit limit", () => {
    render({
      id: "a",
      type: "asset",
      view: "activos",
      columns: ["logo_url", "symbol", "name", "price_usd", "pct24"],
    } as WebComponent);
    expect(container.querySelectorAll("img").length).toBe(8);
    const text = container.textContent ?? "";
    expect(text).toContain("C0");
    expect(text).toContain("Coin 0");
    expect(text).toContain("▲");
    expect(text).toContain("▼");

    act(() => mounted!.unmount());
    mounted = null;
    container.innerHTML = "";

    render({
      id: "a",
      type: "asset",
      view: "activos",
      columns: ["logo_url", "symbol", "name", "price_usd", "pct24"],
      limit: 3,
    } as WebComponent);
    expect(container.querySelectorAll("img").length).toBe(3);
  });

  it("tiles default to half span with xl quarter, overridable by explicit span", () => {
    render({ id: "g", type: "gauge", view: "indicadores", metric: "fear_greed" } as WebComponent);
    const wrapper = container.querySelector('[data-layout-id="g"]') as HTMLElement | null;
    expect(wrapper).not.toBeNull();
    expect(wrapper!.getAttribute("data-layout-span")).toBe("6");
    expect(wrapper!.className).toContain("xl:col-span-3");

    act(() => mounted!.unmount());
    mounted = null;
    container.innerHTML = "";

    render({
      id: "g",
      type: "gauge",
      view: "indicadores",
      metric: "fear_greed",
      span: 12,
    } as WebComponent);
    const wrapper2 = container.querySelector('[data-layout-id="g"]') as HTMLElement | null;
    expect(wrapper2).not.toBeNull();
    expect(wrapper2!.className).not.toContain("xl:col-span-3");
  });

  it("formatValueCompact compacts big magnitudes only", () => {
    expect(formatValueCompact(1234, "number")).toBe(formatValue(1234, "number"));

    const big = formatValueCompact(177441413684, "number");
    expect(big.length).toBeLessThanOrEqual(12);
    expect(big).not.toBe(formatValue(177441413684, "number"));

    const cur = formatValueCompact(2660000000000, "currency", "USD");
    expect(cur).toContain("USD");
    expect(cur.length).toBeLessThan(16);

    expect(formatValueCompact(null, "number")).toBe("—");

    expect(formatValueCompact(61, "percent")).toBe(formatValue(61, "percent"));
  });
});
