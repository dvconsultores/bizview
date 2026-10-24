/** Feature 030 (US3.2, edge case "many filters"): chips reflect the URL state, remove one value,
 * and hand the overflow to the sheet. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReportDefinition } from "../../src/api/types";
import { FilterChips } from "../../src/components/report/FilterChips";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

const def = {
  id: "ventas",
  title: "Ventas",
  description: "",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: { status: { label: "Estatus" }, zone: { label: "Zona" } },
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "none", allowed: ["none"] },
  filters: ["status", "zone"],
  pdf: false,
  ai_narrative: false,
} as ReportDefinition;

async function render(props: Partial<Parameters<typeof FilterChips>[0]>) {
  const onRemove = vi.fn();
  const onMore = vi.fn();
  await act(async () => {
    root?.render(
      <FilterChips def={def} applied={{ period: "mtd", from: "", to: "", compare: "none", filters: {} }} onRemove={onRemove} onMore={onMore} {...props} />,
    );
  });
  return { onRemove, onMore };
}

describe("FilterChips", () => {
  it("renders nothing without applied filters", async () => {
    await render({});
    expect(document.querySelector("ul")).toBeNull();
  });

  it("labels each value with its dimension and removes it on demand", async () => {
    const { onRemove } = await render({
      applied: { period: "mtd", from: "", to: "", compare: "none", filters: { status: ["pagada"], zone: ["norte"] } },
    });
    const chips = Array.from(document.querySelectorAll("button"));
    expect(chips.map((chip) => chip.textContent?.trim())).toEqual([
      "Estatus: pagada",
      "Zona: norte",
    ]);
    await act(async () => chips[1].click());
    expect(onRemove).toHaveBeenCalledWith("zone", "norte");
  });

  it("collapses the overflow into +N más", async () => {
    const filters = { status: ["a", "b", "c", "d", "e", "f", "g"] };
    const { onMore } = await render({
      applied: { period: "mtd", from: "", to: "", compare: "none", filters },
      limit: 6,
    });
    const more = Array.from(document.querySelectorAll("button")).find((el) =>
      el.textContent?.includes(t.reportSheet.moreChips(1)),
    ) as HTMLButtonElement;
    expect(more).toBeTruthy();
    await act(async () => more.click());
    expect(onMore).toHaveBeenCalled();
  });

  it("has an accessible name for each removal", async () => {
    await render({
      applied: { period: "mtd", from: "", to: "", compare: "none", filters: { status: ["pagada"] } },
    });
    const chip = document.querySelector("button") as HTMLButtonElement;
    expect(chip.getAttribute("aria-label")).toBe(t.reportParams.removeFilter("Estatus", "pagada"));
  });
});
