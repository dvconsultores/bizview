import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { LayoutRenderer } from "../../src/components/report/LayoutRenderer";
import { imageKey, imageSrc } from "../../src/components/report/ReportImage";
import type { ReportData, ReportDefinition, WebComponent } from "../../src/api/types";

// Feature 044 — US1: a declared image set reaches the table cell, the asset tile and the KPI tile.

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

const URL_PREFIX = "/api/reports/cripto/assets/coins/";

const def: ReportDefinition = {
  id: "logos",
  title: "Logos",
  currency: "USD",
  metrics: {
    btc: { label: "BTC", format: "currency", better: "higher" },
  },
  dimensions: { symbol: { label: "Símbolo" }, name: { label: "Nombre" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "none", allowed: ["none"] },
  filters: [],
  pdf: true,
  ai_narrative: false,
  images: { coins: { key: "symbol", fallback: "initial", url: URL_PREFIX } },
} as unknown as ReportDefinition;

const rows = [
  { symbol: "BTC", name: "Bitcoin", price: 68000 },
  { symbol: "HYPE/USD", name: "Hyperliquid", price: 12 },
];

const source: ReportData = {
  selection: {
    period: "mtd",
    current: { from: "2026-10-01", to: "2026-10-31" },
    compare: "none",
    previous: null,
    partial: false,
    grain: "day",
  },
  filters: {},
  freshness: { updated_at: null, data_version: "v1" },
  views: [
    {
      id: "monedas",
      type: "table",
      columns: [
        { id: "symbol", label: "Símbolo", kind: "dimension" },
        { id: "name", label: "Nombre", kind: "dimension" },
        { id: "price", label: "Precio", kind: "metric", format: "currency" },
      ],
      rows,
    },
    {
      id: "activos",
      type: "table",
      title: "Activos",
      columns: [
        { id: "symbol", label: "Símbolo", kind: "dimension" },
        { id: "name", label: "Nombre", kind: "dimension" },
        { id: "price", label: "Precio", kind: "metric", format: "currency" },
      ],
      rows,
    },
    {
      id: "cabecera",
      type: "kpis",
      items: [
        {
          metric: "btc",
          label: "BTC",
          format: "currency",
          better: "higher",
          value: 68000,
          previous: null,
          change: null,
        },
      ],
    },
  ],
} as unknown as ReportData;

function mount_(component: WebComponent) {
  mounted = createRoot(container);
  act(() => mounted!.render(<LayoutRenderer layout={{ components: [component] }} data={source} def={def} />));
}

describe("044 images", () => {
  it("a key becomes a file stem the server can look up", () => {
    expect(imageKey("BTC")).toBe("BTC");
    expect(imageKey("HYPE/USD")).toBe("HYPE_USD");
    expect(imageKey(" btc ")).toBe("btc");
    expect(imageKey(null)).toBe("");
  });

  it("the table cell shows a 20 px round image for the keyed column", () => {
    mount_({ id: "t", type: "table", view: "monedas", columns: ["symbol", "name"], image: "coins" } as WebComponent);
    const images = container.querySelectorAll("img");
    expect(images).toHaveLength(2);
    expect(images[0].getAttribute("src")).toBe(`${URL_PREFIX}BTC`);
    expect(images[1].getAttribute("src")).toBe(`${URL_PREFIX}HYPE_USD`);
    expect(images[0].style.width).toBe("20px");
    expect(images[0].className).toContain("rounded-full");
    expect(images[0].getAttribute("alt")).toBe("BTC");
  });

  it("a symbol with no file draws the initial circle instead", () => {
    mount_({ id: "t", type: "table", view: "monedas", columns: ["symbol"], image: "coins" } as WebComponent);
    const first = container.querySelectorAll("img")[0];
    act(() => {
      first.dispatchEvent(new Event("error"));
    });
    const circle = container.querySelector('[role="img"]');
    expect(circle?.textContent).toBe("B");
    expect(circle?.getAttribute("aria-label")).toBe("BTC");
    expect(circle?.className).toContain("bg-chart-");
  });

  it("the asset tile shows a 40 px image and keeps the name and the figure", () => {
    mount_({
      id: "a",
      type: "asset",
      view: "activos",
      columns: ["symbol", "name", null, "price"],
      image: "coins",
    } as unknown as WebComponent);
    const images = container.querySelectorAll("img");
    expect(images).toHaveLength(2);
    expect(images[0].style.width).toBe("40px");
    expect(container.textContent).toContain("Bitcoin");
    expect(container.textContent).toContain("68.000");
  });

  it("the KPI tile draws the set keyed by its metric id", () => {
    mount_({ id: "k", type: "kpi", view: "cabecera", metric: "btc", image: "coins" } as WebComponent);
    expect(container.querySelector("img")?.getAttribute("src")).toBe(`${URL_PREFIX}btc`);
  });

  it("fallback none draws nothing when the file is missing", () => {
    const none = {
      ...def,
      images: { coins: { key: "symbol", fallback: "none", url: URL_PREFIX } },
    } as unknown as ReportDefinition;
    mounted = createRoot(container);
    act(() =>
      mounted!.render(
        <LayoutRenderer
          layout={{ components: [{ id: "t", type: "table", view: "monedas", columns: ["symbol"], image: "coins" } as WebComponent] }}
          data={source}
          def={none}
        />,
      ),
    );
    const first = container.querySelectorAll("img")[0];
    act(() => {
      first.dispatchEvent(new Event("error"));
    });
    expect(container.querySelectorAll("img")).toHaveLength(1);
    expect(container.querySelector('[role="img"]')).toBeNull();
  });

  it("a cached value is read from the report door, never from the third party", () => {
    const set = {
      key: "symbol",
      fallback: "initial",
      column: "l.logo_url",
      cached_url: "/api/reports/cripto/images/",
    } as const;
    const hash = `${"a".repeat(64)}.png`;
    expect(imageSrc(set, hash)).toBe(`/api/reports/cripto/images/${hash}`);
    // A value the worker could not cache keeps its own address: the browser's onError ends it.
    expect(imageSrc(set, "https://cdn.example/x.png")).toBe("https://cdn.example/x.png");
    expect(imageSrc(set, "/site/logo.png")).toBeNull();
    expect(imageSrc(set, "")).toBeNull();
  });

  it("a table cell reads a cached URL column, not the key", () => {
    const cached = {
      ...def,
      images: {
        coins: { key: "symbol", fallback: "initial", url: URL_PREFIX },
        logos: { key: "symbol", fallback: "initial", column: "l.logo_url", cached_url: "/api/reports/r/images/" },
      },
    } as unknown as ReportDefinition;
    const hash = `${"b".repeat(64)}.png`;
    const data = {
      ...source,
      views: [
        {
          id: "monedas",
          type: "table",
          columns: [
            { id: "symbol", label: "Símbolo", kind: "dimension" },
            { id: "logo_url", label: "Logo", kind: "dimension" },
          ],
          rows: [{ symbol: "BTC", logo_url: hash }],
        },
      ],
    } as unknown as ReportData;
    mounted = createRoot(container);
    act(() =>
      mounted!.render(
        <LayoutRenderer
          layout={{ components: [{ id: "t", type: "table", view: "monedas", columns: ["symbol"], image: "logos" } as WebComponent] }}
          data={data}
          def={cached}
        />,
      ),
    );
    expect(container.querySelector("img")?.getAttribute("src")).toBe(`/api/reports/r/images/${hash}`);
  });

  it("the asset comes before the cache when a set declares both", () => {
    const both = {
      ...def,
      images: {
        coins: {
          key: "symbol",
          fallback: "initial",
          url: URL_PREFIX,
          column: "l.logo_url",
          cached_url: "/api/reports/r/images/",
        },
      },
    } as unknown as ReportDefinition;
    mounted = createRoot(container);
    act(() =>
      mounted!.render(
        <LayoutRenderer
          layout={{ components: [{ id: "a", type: "asset", view: "activos", columns: ["symbol"], image: "coins" } as WebComponent] }}
          data={source}
          def={both}
        />,
      ),
    );
    expect(container.querySelector("img")?.getAttribute("src")).toBe(`${URL_PREFIX}BTC`);
  });

  it("no image: keeps today's behaviour", () => {
    mount_({ id: "t", type: "table", view: "monedas", columns: ["symbol"] } as WebComponent);
    expect(container.querySelectorAll("img")).toHaveLength(0);
    expect(container.querySelector('[role="img"]')).toBeNull();
    expect(container.textContent).toContain("BTC");
  });
});
