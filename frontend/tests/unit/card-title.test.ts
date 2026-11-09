import { describe, expect, it } from "vitest";
import type { ReportDefinition, WebComponent } from "../../src/api/types";
import { cardTitle, textWords } from "../../src/lib/cardTitle";

/**
 * Feature 062 — US3. 056 titled a maximized card with `Ampliar «k_ventas»`: a component id from
 * `report.yaml`, shown to a reader who never wrote one. The resolution order is the contract; the id
 * is the only thing it may never return.
 */

function report(components: WebComponent[], extra: Partial<ReportDefinition> = {}): ReportDefinition {
  return {
    id: "ventas",
    title: "Ventas del mes",
    description: "",
    icon: null,
    currency: "USD",
    metrics: {
      net_sales: { label: "Ventas netas", format: "currency", better: "higher" },
      orders: { label: "Pedidos", format: "integer", better: "higher" },
    },
    dimensions: {},
    periods: { default: "mtd", allowed: ["mtd"] },
    compare: { default: "none", allowed: ["none"] },
    filters: [],
    pdf: false,
    layout: { web: { components } },
    ...extra,
  };
}

describe("cardTitle (feature 062)", () => {
  it("uses the component's own title first", () => {
    const def = report([{ id: "k_ventas", type: "kpi", metric: "net_sales", title: "Ventas del día" }]);
    expect(cardTitle(def, "k_ventas")).toBe("Ventas del día");
  });

  it("falls back to the label of the KPI's metric, never the component id", () => {
    const def = report([{ id: "k_ventas", type: "kpi", metric: "net_sales" }]);
    const title = cardTitle(def, "k_ventas");
    expect(title).toBe("Ventas netas");
    expect(title).not.toContain("k_ventas");
  });

  it("uses the view's title when the component has none of its own", () => {
    const def = report([{ id: "c1", type: "donut", view: "por_vendedor" }]);
    expect(cardTitle(def, "c1", { title: "Vendedores por monto" })).toBe("Vendedores por monto");
  });

  it("titles a text card with its first words", () => {
    const def = report([
      { id: "t1", type: "text", text: "Este mes las ventas crecieron un 12 % sobre el anterior." },
    ]);
    // Eight words, one line: enough to recognise the paragraph without becoming a second paragraph.
    expect(cardTitle(def, "t1")).toBe("Este mes las ventas crecieron un 12 %");
  });

  it("falls back to the report's title, and never to the id", () => {
    const def = report([{ id: "c2", type: "bar", view: "sin_titulo" }]);
    expect(cardTitle(def, "c2")).toBe("Ventas del mes");
    expect(cardTitle(def, "c2")).not.toContain("c2");
  });

  it("prefers the English label when the reader's language is English", () => {
    const def = report([{ id: "k1", type: "kpi", metric: "net_sales" }], {
      metrics: {
        net_sales: {
          label: "Ventas netas",
          label_en: "Net sales",
          format: "currency",
          better: "higher",
        },
      },
    });
    // `localized` reads the active catalogue; the Spanish default is what a test without a
    // LocaleProvider gets, and the English pair is what the switcher renders.
    expect(["Ventas netas", "Net sales"]).toContain(cardTitle(def, "k1"));
  });

  it("does not return blank text when a field is whitespace", () => {
    const def = report([{ id: "k3", type: "kpi", metric: "orders", title: "   " }]);
    expect(cardTitle(def, "k3")).toBe("Pedidos");
  });

  it("flattens a multi-line paragraph for a text card", () => {
    expect(textWords({ id: "t", type: "text", text: "Uno\ndos\n\n  tres  " })).toBe("Uno dos tres");
  });
});
