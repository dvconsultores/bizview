/** Feature 053: the non-default parameters as removable chips under the meta line, and the URL
 * contract that keeps them across a reload. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportMetaLine } from "../../src/components/report/ReportMetaLine";
import type { ReportDefinition } from "../../src/api/types";
import { defaultSelection, type ReportSelection } from "../../src/lib/reportQuery";
import { parseViewState, togglePanel, withViewState } from "../../src/lib/reportView";
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
});

const def: ReportDefinition = {
  id: "fixture",
  title: "Fixture",
  description: "Fixture",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: { brand: { label: "Marca" } },
  periods: { default: "mtd", allowed: ["mtd", "last_month"] },
  compare: { default: "none", allowed: ["previous_period"] },
  filters: ["brand"],
  pdf: false,
  ai_narrative: false,
};

function renderMeta(applied: ReportSelection, view: Parameters<typeof ReportMetaLine>[0]["view"]) {
  return act(async () => {
    root.render(
      <ReportMetaLine
        def={def}
        applied={applied}
        data={null}
        onRemoveFilter={vi.fn()}
        onOpenFilters={vi.fn()}
        view={view}
      />,
    );
  });
}

const chips = () =>
  Array.from(container.querySelectorAll('[data-testid="parameter-chips"] button')).map((chip) =>
    chip.getAttribute("aria-label"),
  );

describe("ParameterChips", () => {
  it("shows a chip per non-default parameter and nothing at default", async () => {
    const defaults = defaultSelection(def);
    const onRemove = vi.fn();
    await renderMeta(defaults, {
      theme: null,
      mode: null,
      declaredTheme: "impacto",
      onRemove,
    });
    expect(container.querySelector('[data-testid="parameter-chips"]')).toBeNull();

    await renderMeta(
      { ...defaults, period: "last_month", compare: "previous_period" },
      { theme: "contraste", mode: "dark", declaredTheme: "impacto", onRemove },
    );
    expect(chips()).toEqual([
      t.reportParams.removeParamChip(t.reportParams.chipPeriod, t.reportParams.periodLabels.last_month),
      t.reportParams.removeParamChip(t.reportParams.chipCompare, t.reportParams.compareLabels.previous_period),
      t.reportParams.removeParamChip(t.reportParams.chipPalette, t.palette.contraste),
      t.reportParams.removeParamChip(t.reportParams.chipTheme, t.reportParams.themeDark),
    ]);
  });

  it("reports which chip the reader removed", async () => {
    const onRemove = vi.fn();
    await renderMeta(defaultSelection(def), {
      theme: null,
      mode: "dark",
      declaredTheme: null,
      onRemove,
    });
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-testid="parameter-chips"] button')!.click();
    });
    expect(onRemove).toHaveBeenCalledWith(expect.objectContaining({ key: "mode" }));
  });

  it("ignores a palette equal to the declared one", async () => {
    await renderMeta(defaultSelection(def), {
      theme: "impacto",
      mode: null,
      declaredTheme: "impacto",
      onRemove: vi.fn(),
    });
    expect(container.querySelector('[data-testid="parameter-chips"]')).toBeNull();
  });
});

describe("view state in the URL", () => {
  it("reads and validates theme and mode", () => {
    expect(parseViewState(new URLSearchParams("theme=contraste&mode=dark"))).toEqual({
      theme: "contraste",
      mode: "dark",
    });
    expect(parseViewState(new URLSearchParams("theme=nope&mode=sepia"))).toEqual({
      theme: null,
      mode: null,
    });
  });

  it("switches tabs and closes the one already shown", () => {
    expect(togglePanel(null, "filters")).toBe("filters");
    expect(togglePanel("filters", "params")).toBe("params");
    expect(togglePanel("params", "params")).toBeNull();
  });

  it("sets and removes one key without touching the selection", () => {
    const params = new URLSearchParams("period=mtd&filter.brand=A");
    const withTheme = withViewState(params, { theme: "clasico" });
    expect(withTheme.get("theme")).toBe("clasico");
    expect(withTheme.get("filter.brand")).toBe("A");
    const cleared = withViewState(withTheme, { theme: null });
    expect(cleared.get("theme")).toBeNull();
    expect(withTheme.get("theme")).toBe("clasico"); // the original is not mutated
  });
});
