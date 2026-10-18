import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
      public fields: Record<string, string> = {},
    ) {
      super(message);
    }
  },
  qs: (p: Record<string, string | number | undefined | null>) => {
    const parts = Object.entries(p)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
    return parts.length ? `?${parts.join("&")}` : "";
  },
}));

vi.mock("../../src/lib/download", () => ({
  downloadPdf: vi.fn().mockResolvedValue(undefined),
}));

import { api, ApiError } from "../../src/api/client";
import type { ReportData, ReportDefinition } from "../../src/api/types";
import { AutoRefreshControl } from "../../src/components/report/AutoRefreshControl";
import { ContextBlock } from "../../src/components/report/ContextBlock";
import { formatDateTime } from "../../src/lib/format";
import { freshnessText, isStale, isDirect } from "../../src/lib/freshness";
import { t } from "../../src/i18n/es";
import { Workspace } from "../../src/pages/admin/Workspace";
import { SharedDashboard } from "../../src/pages/SharedDashboard";

let container: HTMLDivElement;
let root: Root | null = null;
beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
  }
  root = null;
  container.remove();
});

async function flush() {
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

const report = {
  id: "ventas", title: "Ventas", description: "Ventas mensuales", icon: null, currency: "USD",
  metrics: {}, dimensions: {},
  periods: { default: "last_month", allowed: ["yesterday", "last_7_days", "last_month", "custom"] },
  compare: { default: "none", allowed: ["none"] },
  filters: [], pdf: true, ai_narrative: false,
} as unknown as ReportDefinition;
const sharedFixture = { dashboard: { code: "ventas", name: "Ventas del mes" }, expires_at: "2026-10-12T12:00:00Z", report };
const reportData: ReportData = {
  selection: { period: "last_month", current: { from: "2026-09-01", to: "2026-09-30" }, compare: "none", previous: null, partial: false, grain: "day" },
  filters: {},
  freshness: { updated_at: "2026-10-05T10:00:00Z", data_version: "v1" },
  views: [],
};

async function renderSharedDashboard(data?: ReportData, error?: ApiError) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === "/api/shared/tok_abc") return sharedFixture;
    if (path.startsWith("/api/shared/tok_abc/data")) {
      if (error) throw error;
      return data ?? reportData;
    }
    throw new Error(`unexpected path ${path}`);
  });
  await act(async () => {
    root?.render(
      <MemoryRouter initialEntries={["/s/tok_abc"]}>
        <Routes><Route path="/s/:token" element={<SharedDashboard />} /></Routes>
      </MemoryRouter>,
    );
  });
  await flush();
}

const directLiveData: ReportData = {
  ...reportData,
  freshness: {
    updated_at: "2026-10-08T15:04:00Z",
    data_version: "v1-d5",
    mode: "direct",
    source: "BI de esta instalación",
    queried_at: "2026-10-08T15:04:00Z",
    stale: false,
  },
};
const directStaleData: ReportData = {
  ...directLiveData,
  freshness: {
    ...directLiveData.freshness,
    stale: true,
    stale_reason: "timeout" as const,
  },
};

describe("freshnessText / isStale", () => {
  it("keeps the dataset wording", () => {
    expect(freshnessText(reportData, report)).toBe(formatDateTime("2026-10-05T10:00:00Z"));
  });

  it("uses notLoaded for dataset data without updated_at", () => {
    const data = { ...reportData, freshness: { updated_at: null, data_version: "v1" } };
    expect(freshnessText(data, report)).toBe(t.reportParams.notLoaded);
  });

  it("returns — for null data", () => {
    expect(freshnessText(null, report)).toBe("—");
  });

  it("renders the live direct line", () => {
    const text = freshnessText(directLiveData, report);
    expect(text).toBe(t.reportParams.live("BI de esta instalación", formatDateTime("2026-10-08T15:04:00Z")));
    expect(text.startsWith("Datos en vivo · BI de esta instalación · consultado ")).toBe(true);
  });

  it("falls back to def.direct.source when freshness.source is missing", () => {
    const data: ReportData = {
      ...directLiveData,
      freshness: { ...directLiveData.freshness, source: undefined },
    };
    const def = { ...report, direct: { source: "Origen del reporte", cache_seconds: 300 } };
    expect(freshnessText(data, def)).toBe(
      t.reportParams.live("Origen del reporte", formatDateTime("2026-10-08T15:04:00Z")),
    );
  });

  it("isStale only for direct stale data", () => {
    expect(isStale({ ...reportData, freshness: { ...reportData.freshness, stale: true } })).toBe(false);
    expect(isStale(directStaleData)).toBe(true);
    expect(isDirect(directStaleData)).toBe(true);
  });
});

describe("ContextBlock direct live text", () => {
  it("renders the live line", async () => {
    await act(async () => {
      root?.render(
        <ContextBlock
          def={report}
          data={directLiveData}
          applied={{ period: "last_month", from: null, to: null, compare: "none", filters: {} }}
          incompleteCustom={false}
          onRemoveFilter={() => {}}
        />,
      );
    });
    expect(container.textContent).toContain("Datos en vivo · BI de esta instalación · consultado ");
  });
});

describe("SharedDashboard direct stale alert", () => {
  it("shows the stale warning inline", async () => {
    await renderSharedDashboard(directStaleData);
    const expected = t.reportParams.stale(formatDateTime("2026-10-08T15:04:00Z"));
    const statuses = Array.from(container.querySelectorAll('[role="status"]'));
    expect(statuses.some((el) => el.textContent === expected)).toBe(true);
  });

  it("does not show stale text for dataset data", async () => {
    await renderSharedDashboard(reportData);
    expect(container.textContent).not.toContain("la fuente no respondió");
  });

  it("shows the server message inline, no dialog", async () => {
    await renderSharedDashboard(undefined, new ApiError(503, "source_unavailable", "No se pudo conectar con la fuente"));
    const alert = container.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("No se pudo conectar con la fuente");
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });
});

describe("AutoRefreshControl direct hint", () => {
  const renderControl = async (cacheSeconds?: number | null) => {
    await act(async () => {
      root?.render(<AutoRefreshControl mode="data" onChange={() => {}} cacheSeconds={cacheSeconds} />);
    });
    return container.querySelector('option[value="data"]')?.textContent;
  };

  it("shows the bucket hint for 5 minutes", async () => {
    expect(await renderControl(300)).toBe(`${t.autoRefresh.modes.data} (${t.autoRefresh.directEvery(5)})`);
  });

  it("rounds 90 seconds up to 2 minutes", async () => {
    expect(await renderControl(90)).toBe(`${t.autoRefresh.modes.data} (${t.autoRefresh.directEvery(2)})`);
  });

  it("is unchanged without cacheSeconds", async () => {
    expect(await renderControl()).toBe(t.autoRefresh.modes.data);
    expect(await renderControl(0)).toBe(t.autoRefresh.modes.data);
  });
});

describe("Workspace report_details card", () => {
  const workspaceState = {
    mounted: null,
    active: {
      id: 3,
      commit: null,
      checksum: "abc",
      applied_at: "2026-10-08T10:00:00Z",
      applied_by: 1,
      workspace: "cliente",
      integrations: [],
      reports: ["ventas", "stock"],
      specs: [],
    },
    previous: null,
    report_details: [
      { id: "stock", mode: "direct", source: "bi", tables: ["public.bi_stock"], status: "broken", last_read_at: "2026-10-08T10:00:00Z" },
      { id: "ventas", mode: "dataset", source: "Origen prueba", tables: ["ventas-prueba.sale_lines"], status: null, last_read_at: null },
    ],
  };

  it("shows mode, source, tables and broken badge", async () => {
    vi.mocked(api.get).mockResolvedValue(workspaceState);
    await act(async () => {
      root?.render(
        <MemoryRouter>
          <Workspace />
        </MemoryRouter>,
      );
    });
    await flush();

    expect(container.textContent).toContain(t.workspace.reports.title);
    expect(container.textContent).toContain(t.workspace.reports.modeDirect);
    expect(container.textContent).toContain(t.workspace.reports.modeDataset);
    expect(container.textContent).toContain(t.workspace.reports.broken);
    expect(container.textContent).toContain("public.bi_stock");
    expect(container.textContent).toContain("Origen prueba");
    expect(container.textContent).not.toContain(t.workspace.reports.failing);

    const heading = Array.from(container.querySelectorAll("h2")).find(
      (h) => h.textContent === t.workspace.reports.title,
    );
    expect(heading).toBeTruthy();
    const card = heading!.closest("div");
    const items = Array.from(card!.querySelectorAll("li"));
    expect(items.length).toBe(2);
    const stock = items.find((li) => li.textContent?.includes("stock"));
    const ventas = items.find((li) => li.textContent?.includes("ventas-prueba.sale_lines"));
    expect(stock?.textContent).toContain(t.workspace.reports.modeDirect);
    expect(stock?.textContent).toContain(t.workspace.reports.broken);
    expect(ventas?.textContent).toContain(t.workspace.reports.modeDataset);
    expect(ventas?.textContent).not.toContain(t.workspace.reports.broken);
  });
});
