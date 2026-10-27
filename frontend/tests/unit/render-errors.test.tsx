import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ReportData, ReportDefinition, ReportView, WebLayout } from "../../src/api/types";
import { LayoutRenderer } from "../../src/components/report/LayoutRenderer";
import { ReportViews } from "../../src/components/report/ReportViews";

// Feature 038 — FR-003/FR-007/FR-009: a tile that cannot render is its own card and the rest of the
// dashboard still draws.

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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
  id: "panorama-cripto",
  title: "Panorama cripto",
  description: "Mercado de criptomonedas",
  icon: null,
  currency: "USD",
  metrics: {
    market_cap: { label: "Capitalización", format: "currency", better: "higher" },
    dominance: { label: "Dominio de la cartera", format: "percent", better: "higher" },
  },
  dimensions: { asset: { label: "Activo" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "none", allowed: ["none"] },
  filters: [],
  pdf: true,
  ai_narrative: false,
};

const card = {
  code: "metric_error" as const,
  message: "La métrica «dominance» no se pudo calcular (division_by_zero).",
  report: "panorama-cripto",
  reference: "e8c808976283",
  metric: "dominance",
  view: "resumen",
  reason: "division_by_zero",
};

const kpis: ReportView = {
  type: "kpis",
  id: "resumen",
  summary: "Capitalización de 1.603 USD.",
  items: [
    {
      metric: "market_cap",
      label: "Capitalización",
      format: "currency",
      better: "higher",
      value: 1603,
      previous: null,
      change: null,
    },
    { metric: "dominance", label: "Dominio de la cartera", format: "percent", better: "higher", value: null, previous: null, change: null, error: card },
  ],
};

const failed: ReportView = {
  type: "trend",
  id: "capitalizacion",
  metric: "market_cap",
  label: "Capitalización",
  format: "currency",
  grain: "day",
  summary: "",
  points: [],
  error: { ...card, message: "Falta el conjunto «mercado-cripto.altcoin_season».", code: "dataset_missing", dataset: "mercado-cripto.altcoin_season" },
};

const data: ReportData = {
  selection: {
    period: "mtd",
    current: { from: "2026-10-01", to: "2026-10-31" },
    compare: "none",
    previous: null,
    partial: false,
    grain: "day",
  },
  filters: {},
  freshness: { updated_at: null, data_version: "preview" },
  render_reference: "e8c808976283",
  views: [kpis, failed],
};

describe("report render error cards (038)", () => {
  it("renders the metric that failed and keeps the rest of the KPI row", () => {
    render(<ReportViews data={data} def={def} />);
    const text = container.textContent ?? "";
    expect(text).toContain("1603");
    expect(text).toContain("La métrica «dominance» no se pudo calcular");
    expect(text).toContain("Detalles técnicos");
  });

  it("names the code, the report, the reference and the failing ids in the technical details", () => {
    render(<ReportViews data={data} def={def} />);
    const text = container.textContent ?? "";
    expect(text).toContain("metric_error");
    expect(text).toContain("panorama-cripto");
    expect(text).toContain("e8c808976283");
    expect(text).toContain("dominance");
    expect(text).toContain("docker logs --tail 500 bizview-backend | grep -n \"e8c808976283\"");
  });

  it("renders one component's card while the other components still draw", () => {
    const layout: WebLayout = {
      gutter: "md",
      components: [
        { id: "grafico", type: "line", view: "capitalizacion", x: "day", series: ["market_cap"] },
        { id: "resumen_kpi", type: "kpi", view: "resumen", metric: "market_cap" },
      ],
    };
    render(<LayoutRenderer layout={layout} data={data} def={def} />);
    const cells = Array.from(container.querySelectorAll<HTMLElement>("[data-layout-id]"));
    expect(cells.map((cell) => cell.dataset.layoutId)).toEqual(["grafico", "resumen_kpi"]);
    expect(cells[0].textContent).toContain("Falta el conjunto «mercado-cripto.altcoin_season».");
    expect(cells[1].textContent).toContain("1603");
  });

  it("says «Sin datos» for an empty view instead of failing it", () => {
    const empty: ReportData = {
      ...data,
      views: [
        { ...kpis, items: kpis.items.filter((item) => !item.error),
          empty: { code: "empty_dataset", message: "Sin datos: mercado-cripto.altcoin_season no tiene filas en el período.", datasets: "mercado-cripto.altcoin_season" } },
      ],
    };
    render(<ReportViews data={empty} def={def} />);
    expect(container.textContent).toContain("Sin datos: mercado-cripto.altcoin_season");
  });
});
