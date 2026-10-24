import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ParamsForm } from "../../src/components/report/ParamsForm";
import type { ReportDefinition } from "../../src/api/types";
import { defaultSelection, type ReportSelection } from "../../src/lib/reportQuery";
import { t } from "../../src/i18n/es";
import type { MultiSelectOptions } from "../../src/components/MultiSelect";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
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

const fixtureDef: ReportDefinition = {
  id: "fixture",
  title: "Fixture Report",
  description: "Fixture",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: {
    brand: { label: "Marca" },
  },
  periods: {
    default: "mtd",
    allowed: ["mtd", "last_month", "custom"],
  },
  compare: {
    default: "none",
    allowed: ["previous_period", "previous_year"],
  },
  filters: ["brand"],
  pdf: false,
  ai_narrative: false,
};

const appliedSelection: ReportSelection = {
  period: "mtd",
  from: "",
  to: "",
  compare: "none",
  filters: {},
};

function findFieldByLabel(labelText: string): HTMLElement {
  const label = Array.from(document.querySelectorAll("label")).find(
    (el) => el.textContent?.trim() === labelText,
  );
  expect(label, `label "${labelText}" should exist`).toBeTruthy();
  const htmlFor = label!.getAttribute("for");
  expect(htmlFor, `label "${labelText}" should have htmlFor`).toBeTruthy();
  const field = document.getElementById(htmlFor!);
  expect(field, `field for label "${labelText}" should exist`).toBeTruthy();
  return field!;
}

function changeSelect(select: HTMLSelectElement, value: string) {
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(
    select,
    value,
  );
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function changeInput(input: HTMLInputElement, value: string) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(
    input,
    value,
  );
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

async function renderForm(overrides: {
  def?: Partial<ReportDefinition>;
  applied?: ReportSelection;
  live?: boolean;
  section?: "all" | "period" | "filters";
  loadOptions?: (
    filterId: string,
    period: ReportSelection,
    q: string,
    signal: AbortSignal,
  ) => Promise<MultiSelectOptions>;
}) {
  const def = {
    ...fixtureDef,
    ...overrides.def,
    periods: {
      ...fixtureDef.periods,
      ...(overrides.def?.periods ?? {}),
    },
    compare: {
      ...fixtureDef.compare,
      ...(overrides.def?.compare ?? {}),
    },
  } as ReportDefinition;

  const applied = overrides.applied ?? appliedSelection;
  const loadOptions =
    overrides.loadOptions ??
    vi.fn(async () => ({ items: [], truncated: false }));

  const onApply = vi.fn();

  await act(async () => {
    root.render(
      <ParamsForm
        def={def}
        applied={applied}
        onApply={onApply}
        loadOptions={loadOptions}
        live={overrides.live}
        section={overrides.section}
      />,
    );
  });

  return { def, applied, loadOptions, onApply };
}

describe("ParamsForm", () => {
  it("three edits (period, compare, filter) show pending text and applying calls onApply exactly once with all three", async () => {
    const brandOptions = vi
      .fn()
      .mockResolvedValue({ items: ["Nike", "Adidas"], truncated: false });

    const { onApply } = await renderForm({
      loadOptions: brandOptions,
    });

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    changeSelect(periodSelect, "last_month");

    const compareSelect = findFieldByLabel(t.reportParams.compare) as HTMLSelectElement;
    changeSelect(compareSelect, "previous_year");

    const brandMultiSelect = findFieldByLabel("Marca") as HTMLInputElement;
    await act(async () => {
      brandMultiSelect.focus();
    });

    await act(async () => {
      await Promise.resolve();
    });

    const option = document.querySelector('[role="option"]');
    expect(option, "brand option should render").toBeTruthy();
    await act(async () => {
      option!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const pendingStatus = document.querySelector(
      '[data-testid="pending-status"]',
    );
    expect(pendingStatus?.textContent).toContain("3 cambios sin aplicar");

    const submitButton = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent === t.reportParams.apply,
    ) as HTMLButtonElement;
    expect(submitButton.disabled).toBe(false);

    await act(async () => {
      submitButton.click();
    });

    expect(onApply).toHaveBeenCalledTimes(1);
    const appliedArg = onApply.mock.calls[0][0] as ReportSelection;
    expect(appliedArg.period).toBe("last_month");
    expect(appliedArg.compare).toBe("previous_year");
    expect(appliedArg.filters).toEqual({ brand: ["Nike"] });
  });

  it("custom period with Hasta before Desde shows error and does not apply; missing date also errors", async () => {
    const { onApply } = await renderForm({});

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    changeSelect(periodSelect, "custom");

    const fromInput = findFieldByLabel(t.reportParams.from) as HTMLInputElement;
    const toInput = findFieldByLabel(t.reportParams.to) as HTMLInputElement;

    changeInput(fromInput, "2025-05-10");
    changeInput(toInput, "2025-05-01");

    const submitButton = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent === t.reportParams.apply,
    ) as HTMLButtonElement;

    await act(async () => {
      submitButton.click();
    });

    expect(onApply).not.toHaveBeenCalled();
    const errorText = document.body.textContent ?? "";
    expect(errorText).toContain(t.reportParams.toBeforeFrom);

    changeInput(toInput, "");
    await act(async () => {
      submitButton.click();
    });

    expect(onApply).not.toHaveBeenCalled();
    expect(document.body.textContent ?? "").toContain(t.reportParams.toRequired);
  });

  it("Limpiar todo with non-default applied shows defaults and calls onApply once with defaultSelection", async () => {
    const nonDefault: ReportSelection = {
      period: "last_month",
      from: "",
      to: "",
      compare: "previous_year",
      filters: { brand: ["Nike"] },
    };

    const defaultSelectionObj = defaultSelection(fixtureDef);

    const { onApply } = await renderForm({
      applied: nonDefault,
      loadOptions: vi.fn().mockResolvedValue({ items: ["Nike"], truncated: false }),
    });

    const clearButton = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent === t.reportParams.clear,
    ) as HTMLButtonElement;

    await act(async () => {
      clearButton.click();
    });

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledWith(defaultSelectionObj);

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    expect(periodSelect.value).toBe("mtd");

    const compareSelect = findFieldByLabel(t.reportParams.compare) as HTMLSelectElement;
    expect(compareSelect.value).toBe("none");

    const brandInput = findFieldByLabel("Marca") as HTMLInputElement;
    expect(brandInput.value).toBe("");
  });

  it("Aplicar filtros is disabled with no pending changes", async () => {
    await renderForm({});

    const submitButton = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent === t.reportParams.apply,
    ) as HTMLButtonElement;

    expect(submitButton.disabled).toBe(true);
  });

  it("read-only compare when def.compare.allowed is empty", async () => {
    await renderForm({
      def: {
        compare: { default: "none", allowed: [] },
      },
    });

    const compareField = findFieldByLabel(t.reportParams.compare) as HTMLInputElement;
    expect(compareField.readOnly).toBe(true);
    expect(compareField.value).toBe(t.reportParams.compareLabels.none);
  });

  it("read-only compare when only previous_year is allowed", async () => {
    await renderForm({
      def: {
        compare: { default: "previous_year", allowed: ["previous_year"] },
      },
      applied: {
        period: "mtd",
        from: "",
        to: "",
        compare: "previous_year",
        filters: {},
      },
    });

    const compareField = findFieldByLabel(t.reportParams.compare) as HTMLInputElement;
    expect(compareField.tagName).toBe("INPUT");
    expect(compareField.readOnly).toBe(true);
    expect(compareField.value).toBe(t.reportParams.compareLabels.previous_year);
    expect(document.querySelector("select option[value='none']")).toBeNull();
  });

  it("compare select offers only the allowed choices", async () => {
    await renderForm({
      def: {
        compare: { default: "previous_period", allowed: ["previous_period", "previous_year"] },
      },
      applied: {
        period: "mtd",
        from: "",
        to: "",
        compare: "previous_period",
        filters: {},
      },
    });

    const compareSelect = findFieldByLabel(t.reportParams.compare) as HTMLSelectElement;
    const optionValues = Array.from(compareSelect.options).map((option) => option.value);
    expect(optionValues).toEqual(["previous_period", "previous_year"]);
  });

  it("no Filtros section when def.filters is empty", async () => {
    await renderForm({
      def: {
        filters: [],
      },
    });

    expect(document.body.textContent ?? "").not.toContain(
      t.reportParams.filtersSection,
    );
  });

  it("resets draft when applied changes externally", async () => {
    const { onApply } = await renderForm({});

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    changeSelect(periodSelect, "last_month");

    const newApplied: ReportSelection = {
      period: "last_month",
      from: "",
      to: "",
      compare: "none",
      filters: {},
    };

    await act(async () => {
      root.render(
        <ParamsForm
          def={fixtureDef}
          applied={newApplied}
          onApply={onApply}
          loadOptions={vi.fn().mockResolvedValue({ items: [], truncated: false })}
        />,
      );
    });

    const refreshedPeriod = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    expect(refreshedPeriod.value).toBe("last_month");

    const pendingStatus = document.querySelector(
      '[data-testid="pending-status"]',
    );
    expect(pendingStatus?.textContent).toContain(t.reportParams.noPending);
  });

  it("custom period with missing dates shows errors when trying to apply", async () => {
    const { onApply } = await renderForm({});

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    changeSelect(periodSelect, "custom");

    const submitButton = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent === t.reportParams.apply,
    ) as HTMLButtonElement;

    await act(async () => {
      submitButton.click();
    });

    expect(onApply).not.toHaveBeenCalled();
    const text = document.body.textContent ?? "";
    expect(text).toContain(t.reportParams.fromRequired);
    expect(text).toContain(t.reportParams.toRequired);
  });

  it("live: a complete change applies once after the 250 ms debounce", async () => {
    vi.useFakeTimers();
    const { onApply } = await renderForm({ live: true });

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    await act(async () => {
      changeSelect(periodSelect, "last_month");
    });
    expect(onApply).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(260);
    });
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0].period).toBe("last_month");
    vi.useRealTimers();
  });

  it("live: an incomplete custom range is never applied", async () => {
    vi.useFakeTimers();
    const { onApply } = await renderForm({ live: true });

    const periodSelect = findFieldByLabel(t.reportParams.period) as HTMLSelectElement;
    await act(async () => {
      changeSelect(periodSelect, "custom");
    });
    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    expect(onApply).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('section="filters" renders only the filters block', async () => {
    await renderForm({ section: "filters" });
    expect(document.body.textContent).not.toContain(t.reportParams.periodSection);
    expect(document.body.textContent).toContain(t.reportParams.filtersSection);
    expect(findFieldByLabel("Marca")).toBeTruthy();
  });

  it('section="period" renders only the period and comparison blocks', async () => {
    await renderForm({ section: "period" });
    expect(document.body.textContent).toContain(t.reportParams.periodSection);
    expect(document.body.textContent).not.toContain(t.reportParams.filtersSection);
  });

  it("groups the tail of a long filter list under a collapsible heading", async () => {
    const filters = Array.from({ length: 11 }, (_, i) => `f${i}`);
    const dimensions = Object.fromEntries(filters.map((id) => [id, { label: id.toUpperCase() }]));
    await renderForm({ def: { filters, dimensions }, section: "filters" });
    expect(document.body.textContent).toContain(t.reportSheet.moreFilters(5));
    expect(document.querySelector("details")).toBeTruthy();
  });
});
