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
import { downloadPdf } from "../../src/lib/download";
import { SharedDashboard } from "../../src/pages/SharedDashboard";
import { t } from "../../src/i18n/es";

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
    try {
      await act(async () => root?.unmount());
    } catch {
      // already unmounted in the robots-meta test
    }
  }
  root = null;
  container.remove();
  vi.useRealTimers();
});

async function flush() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}
const byText = (text: string) =>
  Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === text,
  ) as HTMLButtonElement | undefined;

const report = {
  id: "ventas",
  title: "Ventas",
  description: "Ventas mensuales",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: {},
  periods: {
    default: "last_month",
    allowed: ["yesterday", "last_7_days", "last_month", "custom"],
  },
  compare: { default: "none", allowed: ["none"] },
  filters: [],
  pdf: true,
  ai_narrative: false,
};

const sharedFixture = {
  dashboard: { code: "ventas", name: "Ventas del mes" },
  expires_at: "2026-10-12T12:00:00Z",
  report,
};

const reportData = {
  selection: {
    period: "last_month",
    current: { from: "2026-09-01", to: "2026-09-30" },
    compare: "none",
    previous: null,
    partial: false,
    grain: "day",
  },
  filters: {},
  freshness: { updated_at: "2026-10-05T10:00:00Z", data_version: "v1" },
  views: [],
};

async function renderPage() {
  await act(async () => {
    root?.render(
      <MemoryRouter initialEntries={["/s/tok_abc"]}>
        <Routes>
          <Route path="/s/:token" element={<SharedDashboard />} />
        </Routes>
      </MemoryRouter>,
    );
  });
  await flush();
}

describe("SharedDashboard", () => {
  it("shows neutral expired page for 404", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new ApiError(404, "not_found", "Este enlace expiró o fue revocado."),
    );
    await renderPage();

    expect(container.textContent).toContain(t.sharing.shared.expiredTitle);
    expect(container.textContent).not.toContain("Ventas");
    expect(container.querySelector("a")).toBeNull();
  });

  it("shows throttled page and retries", async () => {
    let definitionCalls = 0;
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/shared/tok_abc") {
        definitionCalls += 1;
        if (definitionCalls === 1) {
          throw new ApiError(
            429,
            "rate_limited",
            "Demasiadas visitas.",
          );
        }
        return sharedFixture;
      }
      if (path.startsWith("/api/shared/tok_abc/data")) {
        return reportData;
      }
      throw new Error(`unexpected path ${path}`);
    });
    await renderPage();

    expect(container.textContent).toContain(t.sharing.shared.tooManyTitle);
    expect(byText(t.common.retry)).toBeDefined();

    await act(async () => {
      byText(t.common.retry)?.click();
    });
    await flush();

    const definitionCallCount = vi
      .mocked(api.get)
      .mock.calls.filter(([path]) => path === "/api/shared/tok_abc").length;
    expect(definitionCallCount).toBe(2);
    expect(container.textContent).toContain("Ventas del mes");
  });

  it("loads dashboard, sets robots meta, and removes it on unmount", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/shared/tok_abc") return sharedFixture;
      if (path.startsWith("/api/shared/tok_abc/data")) return reportData;
      throw new Error(`unexpected path ${path}`);
    });
    await renderPage();

    const h1 = Array.from(container.querySelectorAll("h1")).find(
      (n) => n.textContent?.includes("Ventas del mes"),
    );
    expect(h1).toBeDefined();
    expect(container.textContent).toContain("Vista compartida");

    const dataCall = vi
      .mocked(api.get)
      .mock.calls.find(([path]) =>
        String(path).startsWith("/api/shared/tok_abc/data?"),
      );
    expect(dataCall).toBeDefined();
    expect(String(dataCall?.[0])).toContain("period=last_month");

    const robots = Array.from(
      document.head.querySelectorAll('meta[name="robots"]'),
    ).find((meta) => meta.getAttribute("content") === "noindex, nofollow");
    expect(robots).toBeDefined();

    await act(async () => {
      root?.unmount();
    });
    root = null;
    expect(
      Array.from(document.head.querySelectorAll('meta[name="robots"]')).some(
        (meta) => meta.getAttribute("content") === "noindex, nofollow",
      ),
    ).toBe(false);
  });

  it("downloads PDF with the selection query and range filename", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/shared/tok_abc") return sharedFixture;
      if (path.startsWith("/api/shared/tok_abc/data")) return reportData;
      throw new Error(`unexpected path ${path}`);
    });
    await renderPage();

    await act(async () => {
      byText(t.reportParams.downloadPdf)?.click();
    });
    await flush();

    expect(vi.mocked(downloadPdf)).toHaveBeenCalledWith(
      expect.stringMatching(
        /^\/api\/shared\/tok_abc\/pdf\?.*period=last_month/,
      ),
      "ventas-2026-09-01-2026-09-30.pdf",
      t.reportParams.pdfError,
    );
  });

  it("switches to expired page when the data request 404s", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/shared/tok_abc") return sharedFixture;
      if (path.startsWith("/api/shared/tok_abc/data")) {
        throw new ApiError(
          404,
          "not_found",
          "Este enlace expiró o fue revocado.",
        );
      }
      throw new Error(`unexpected path ${path}`);
    });
    await renderPage();

    expect(container.textContent).toContain(t.sharing.shared.expiredTitle);
    expect(container.textContent).not.toContain("Ventas del mes");
  });
});
