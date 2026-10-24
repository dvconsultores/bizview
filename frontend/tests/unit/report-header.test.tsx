/** Feature 030 (US2, FR-002/FR-005): the meta line replaces the parameters card, the actions row
 * collapses by breakpoint, and "Consultado por" is gone from the screen. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FileDown, Share2, Tv } from "lucide-react";
import type { ReportData, ReportDefinition } from "../../src/api/types";
import { ReportActions } from "../../src/components/report/ReportActions";
import { ReportMetaLine } from "../../src/components/report/ReportMetaLine";
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

const def: ReportDefinition = {
  id: "ventas",
  title: "Ventas",
  description: "Ventas y facturación",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: { status: { label: "Estatus" } },
  periods: { default: "ytd", allowed: ["ytd", "mtd", "custom"] },
  compare: { default: "previous_year", allowed: ["none", "previous_year"] },
  filters: ["status"],
  pdf: true,
  ai_narrative: false,
};

const data = {
  selection: {
    current: { from: "2026-01-01", to: "2026-10-23" },
    previous: { from: "2025-01-01", to: "2025-10-23" },
    period: "ytd",
    compare: "previous_year",
    filters: {},
  },
  freshness: { updated_at: "2026-10-23T20:00:00Z", mode: "dataset", data_version: "v1" },
} as unknown as ReportData;

const applied = {
  period: "ytd" as const,
  from: "",
  to: "",
  compare: "previous_year" as const,
  filters: {},
};

describe("ReportMetaLine", () => {
  it("reads period · range · comparison · updated in one line", async () => {
    await act(async () => {
      root?.render(
        <ReportMetaLine def={def} applied={applied} data={data} onRemoveFilter={() => {}} onOpenFilters={() => {}} />,
      );
    });
    const text = document.querySelector('[data-testid="report-meta-line"]')?.textContent ?? "";
    expect(text).toContain(t.reportParams.periodLabels.ytd);
    expect(text).toContain("2026");
    expect(text).toContain(t.reportParams.metaCompared);
    expect(text).toContain("2025");
  });

  it("never renders the viewer on screen", async () => {
    await act(async () => {
      root?.render(
        <ReportMetaLine def={def} applied={applied} data={data} onRemoveFilter={() => {}} onOpenFilters={() => {}} />,
      );
    });
    expect(document.body.textContent).not.toContain("Consultado por");
    expect(document.body.textContent).not.toContain("Viewed by");
  });

  it("shows the applied filters as removable chips", async () => {
    const onRemove = vi.fn();
    await act(async () => {
      root?.render(
        <ReportMetaLine
          def={def}
          applied={{ ...applied, filters: { status: ["pagada"] } }}
          data={data}
          onRemoveFilter={onRemove}
          onOpenFilters={() => {}}
        />,
      );
    });
    const chip = Array.from(document.querySelectorAll("button")).find((el) =>
      el.textContent?.includes("pagada"),
    ) as HTMLButtonElement;
    expect(chip).toBeTruthy();
    await act(async () => chip.click());
    expect(onRemove).toHaveBeenCalledWith("status", "pagada");
  });
});

describe("ReportActions", () => {
  const base = {
    activeFilters: 2,
    onOpenFilters: vi.fn(),
    onOpenParams: vi.fn(),
    actions: [
      { id: "pdf", label: t.reportActions.pdf, icon: FileDown, onClick: vi.fn(), show: true },
      { id: "share", label: t.reportActions.share, icon: Share2, onClick: vi.fn(), show: false },
      { id: "tv", label: t.reportActions.tv, icon: Tv, onClick: vi.fn(), show: true },
    ],
  };

  it("always offers Filtros (with its count) and Parámetros", async () => {
    await act(async () => {
      root?.render(<ReportActions {...base} />);
    });
    const labels = Array.from(document.querySelectorAll("button")).map((el) => el.textContent ?? "");
    expect(labels.some((label) => label.includes(t.reportActions.filters(2)))).toBe(true);
    expect(labels.some((label) => label.includes(t.reportActions.params))).toBe(true);
  });

  it("hides actions whose condition is false (no dashboard, no share)", async () => {
    await act(async () => {
      root?.render(<ReportActions {...base} />);
    });
    const text = document.body.textContent ?? "";
    expect(text).not.toContain(t.reportActions.share);
    expect(text).toContain(t.reportActions.pdf);
  });

  it("opens the phone menu with the collapsed actions and closes on Escape", async () => {
    await act(async () => {
      root?.render(<ReportActions {...base} />);
    });
    const trigger = document.querySelector('[aria-haspopup="menu"]') as HTMLButtonElement;
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    await act(async () => trigger.click());
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const items = document.querySelectorAll('[role="menuitem"]');
    expect(items).toHaveLength(2);
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(document.querySelector('[role="menu"]')).toBeNull();
  });

  it("marks the buttons that open the sheet so its outside-click ignores them", async () => {
    await act(async () => {
      root?.render(<ReportActions {...base} />);
    });
    expect(document.querySelectorAll("[data-sheet-opener]")).toHaveLength(2);
  });
});
