/** Feature 053: the Parámetros tab of the report sheet — five rows in order, the theme row only
 * when the report declares a theme, and a change made just before closing is not lost. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportParamsPanel } from "../../src/components/report/ReportParamsPanel";
import type { ReportDefinition } from "../../src/api/types";
import { defaultSelection, type ReportSelection } from "../../src/lib/reportQuery";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
});

const def: ReportDefinition = {
  id: "fixture",
  title: "Fixture",
  description: "Fixture",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: { brand: { label: "Marca" } },
  periods: { default: "mtd", allowed: ["mtd", "last_month", "custom"] },
  compare: { default: "none", allowed: ["previous_period", "previous_year"] },
  filters: ["brand"],
  pdf: false,
  ai_narrative: false,
};

const applied: ReportSelection = defaultSelection(def);

function labels() {
  return Array.from(container.querySelectorAll("label")).map((label) => label.textContent?.trim());
}

function field(label: string): HTMLElement {
  const found = Array.from(container.querySelectorAll("label")).find(
    (item) => item.textContent?.trim() === label,
  );
  const forId = found?.getAttribute("for");
  const control = forId ? container.querySelector<HTMLElement>(`#${forId}`) : null;
  if (!control) throw new Error(`no field labelled ${label}`);
  return control;
}

async function renderPanel(extra: Partial<Parameters<typeof ReportParamsPanel>[0]> = {}) {
  const onApply = vi.fn();
  await act(async () => {
    root.render(
      <ReportParamsPanel
        def={def}
        applied={applied}
        onApply={onApply}
        loadOptions={async () => []}
        {...extra}
      />,
    );
  });
  return { onApply };
}

describe("ReportParamsPanel", () => {
  it("lists period, comparison, refresh, palette and theme, in that order", async () => {
    await renderPanel({
      refresh: { mode: "off", onChange: vi.fn() },
      palette: { value: null, onChange: vi.fn() },
      themeMode: { value: null, onChange: vi.fn() },
    });
    const shown = labels();
    const order = [
      t.reportParams.period,
      t.reportParams.compare,
      t.autoRefresh.frequency,
      t.palette.label,
      t.reportParams.theme,
    ].map((label) => shown.indexOf(label));
    expect(order.every((index) => index >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("hides the theme row when the report declares no theme", async () => {
    await renderPanel({ refresh: { mode: "off", onChange: vi.fn() } });
    expect(labels()).not.toContain(t.reportParams.theme);
  });

  it("shows the palette swatches of the selected theme", async () => {
    await renderPanel({ palette: { value: "contraste", onChange: vi.fn() } });
    const swatches = container.querySelector('[data-testid="palette-swatches"]');
    expect(swatches).toBeTruthy();
    expect(swatches!.children.length).toBe(8);
  });

  it("offers the comparison read-only when the report allows a single option", async () => {
    const single: ReportDefinition = { ...def, compare: { default: "none", allowed: [] } };
    await act(async () => {
      root.render(
        <ReportParamsPanel def={single} applied={applied} onApply={vi.fn()} loadOptions={async () => []} />,
      );
    });
    expect(labels()).toContain(t.reportParams.compare);
    expect(container.querySelectorAll("select").length).toBe(1); // only Período
  });

  it("applies a pending change when the panel closes (no lost edit)", async () => {
    vi.useFakeTimers();
    const { onApply } = await renderPanel();
    const period = field(t.reportParams.period) as HTMLSelectElement;
    await act(async () => {
      period.value = "last_month";
      period.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onApply).not.toHaveBeenCalled();
    await act(async () => {
      root.render(<p>cerrado</p>); // the sheet closes before the 250 ms elapse
    });
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0].period).toBe("last_month");
  });
});
