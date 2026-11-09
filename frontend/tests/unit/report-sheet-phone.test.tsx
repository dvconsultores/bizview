/** Feature 059: the Filtros | Parámetros sheet on a phone — density, one label per control, the
 * period/comparison row, the chip rows and the searchable filter. Geometry (the sheet filling the
 * viewport, the footer never covering the last control) is measured in
 * `tests/e2e/mobile-first.spec.ts`; jsdom only sees classes and roles. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReportDefinition } from "../../src/api/types";
import { ReportParamsPanel } from "../../src/components/report/ReportParamsPanel";
import { ReportSheet } from "../../src/components/report/ReportSheet";
import { defaultSelection, type ReportSelection } from "../../src/lib/reportQuery";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
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
  periods: { default: "mtd", allowed: ["mtd", "last_month", "custom"] },
  compare: { default: "none", allowed: ["previous_period", "previous_year"] },
  filters: ["brand"],
  pdf: false,
  ai_narrative: false,
};

const applied: ReportSelection = defaultSelection(def);

async function renderPanel(extra: Partial<Parameters<typeof ReportParamsPanel>[0]> = {}) {
  await act(async () => {
    root.render(
      <ReportParamsPanel
        def={def}
        applied={applied}
        onApply={vi.fn()}
        loadOptions={async () => []}
        {...extra}
      />,
    );
  });
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

function ancestorWith(el: Element, token: string): HTMLElement {
  let node: Element | null = el;
  while (node) {
    if (typeof (node as HTMLElement).className === "string" && (node as HTMLElement).className.includes(token)) {
      return node as HTMLElement;
    }
    node = node.parentElement;
  }
  throw new Error(`no ancestor with ${token}`);
}

describe("the Parámetros tab on a phone", () => {
  it("drops the repeated section titles from the screen but keeps them for a screen reader", async () => {
    await renderPanel();
    const headings = Array.from(container.querySelectorAll("h3")).map((h) => h.textContent?.trim());
    expect(headings).toContain(t.reportParams.periodSection);
    // Hidden below 640 px only: the label of the control already says the same words.
    for (const heading of Array.from(container.querySelectorAll("h3"))) {
      if (heading.textContent?.trim() === t.reportParams.filtersSection) continue;
      expect(heading.className).toContain("max-sm:sr-only");
    }
  });

  it("puts the period and the comparison on one row from 320 px", async () => {
    // Feature 062: the threshold was 160 px, which needed 332 px for two columns plus the gap — more
    // than a 360 px phone has after its gutter, so the pair stacked and every control looked narrow.
    await renderPanel();
    const row = ancestorWith(field(t.reportParams.period), "max-sm:grid-cols-[repeat");
    expect(row.className).toContain("max-sm:grid-cols-[repeat(auto-fit,minmax(130px,1fr))]");
    // Both controls live in that row.
    expect(row.contains(field(t.reportParams.compare))).toBe(true);
  });

  it("keeps the custom range in its own two-column row below the period", async () => {
    await renderPanel();
    const onApply = vi.fn();
    await act(async () => {
      const select = field(t.reportParams.period) as HTMLSelectElement;
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!;
      setter.call(select, "custom");
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const from = field(t.reportParams.from);
    const to = field(t.reportParams.to);
    const row = ancestorWith(from, "min-[360px]:grid-cols-2");
    expect(row).toBe(ancestorWith(to, "min-[360px]:grid-cols-2"));
    expect(row.className).toContain("min-[360px]:grid-cols-2");
    expect(row.className).toContain("max-sm:col-span-full");
    expect(onApply).not.toHaveBeenCalled();
  });

  it("tightens the gaps to 12 px on phones without changing the desktop spacing", async () => {
    await renderPanel();
    const form = container.querySelector('[data-testid="params-form"]') as HTMLElement;
    const stack = form.firstElementChild as HTMLElement;
    expect(stack.className).toContain("space-y-4");
    expect(stack.className).toContain("max-sm:space-y-3");
  });

  it("replaces the palette and theme selects with one chip row each on phones", async () => {
    await renderPanel({
      refresh: { mode: "off", onChange: vi.fn() },
      palette: { value: null, onChange: vi.fn() },
      themeMode: { value: null, onChange: vi.fn() },
    });
    const palette = container.querySelector('[data-testid="palette-chips"]') as HTMLElement;
    const theme = container.querySelector('[data-testid="theme-chips"]') as HTMLElement;
    expect(palette).not.toBeNull();
    expect(theme).not.toBeNull();
    // One line each, scrollable sideways, 44 px targets.
    const paletteRow = palette.querySelector('[role="group"]') as HTMLElement;
    expect(paletteRow.className).toContain("overflow-x-auto");
    const chips = Array.from(paletteRow.querySelectorAll("button"));
    expect(chips.length).toBeGreaterThan(1);
    expect(chips[0].className).toContain("min-h-tap");
    expect(chips[0].getAttribute("aria-pressed")).toBe("true");
    // The select stays for wide screens on the same state.
    const selects = Array.from(container.querySelectorAll("select")).filter(
      (select) => select.closest(".max-sm\\:hidden") !== null,
    );
    expect(selects.length).toBe(2);
  });

  it("applies a palette chip to the same value the select would", async () => {
    const onChange = vi.fn();
    await renderPanel({ palette: { value: null, onChange } });
    const chips = Array.from(
      container.querySelectorAll('[data-testid="palette-chips"] button'),
    ) as HTMLButtonElement[];
    await act(async () => chips[1].click());
    expect(onChange).toHaveBeenCalledWith("impacto");
  });
});

describe("the Filtros tab on a phone", () => {
  it("shows the selected values as chips above a searchable list", async () => {
    await act(async () => {
      root.render(
        <ReportSheet
          open
          title="Filtros"
          onClose={() => {}}
          tabs={[
            { id: "filters", label: t.reportSheet.tabs.filters },
            { id: "params", label: t.reportSheet.tabs.params },
          ]}
          tab="filters"
          onTabChange={() => {}}
        >
          <div>contenido</div>
        </ReportSheet>,
      );
    });
    const panel = container.querySelector('[data-testid="report-sheet"]') as HTMLElement;
    // Tabs on the left, close on the right, one row: no drag handle on a full-screen sheet.
    const header = panel.children[1] as HTMLElement;
    const tablist = header.querySelector('[role="tablist"]') as HTMLElement;
    expect(tablist).not.toBeNull();
    expect(header.lastElementChild?.getAttribute("aria-label")).toBe(t.reportSheet.close);
    expect(header.lastElementChild?.className).toContain("min-h-tap");
    expect(panel.querySelector('[role="region"]')).toBeNull();
  });
});
