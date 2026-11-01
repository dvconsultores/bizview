/** Feature 047 (US4): a report paints from its own theme, its own mode, and the viewer's toggle —
 * light and dark land on the report's area, the chrome stays as the viewer chose, and the share
 * link opens in the report's mode. */
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
      public retries?: number,
      public details: Record<string, unknown> = {},
    ) {
      super(message);
    }
  },
}));

vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: null, setUser: vi.fn() }),
}));

vi.mock("../../src/components/Toast", () => ({ useToast: () => vi.fn() }));
vi.mock("../../src/lib/download", () => ({ downloadPdf: vi.fn().mockResolvedValue(undefined) }));

import { api } from "../../src/api/client";
import { SharedDashboard } from "../../src/pages/SharedDashboard";
import { ThemeProvider } from "../../src/theme/ThemeContext";
import { knownTheme, reportMode, reportThemeId } from "../../src/theme/library";
import { BUILTIN_THEMES, deriveTokens } from "../../src/theme/themes";
import { t } from "../../src/i18n/es";
import { STORAGE_KEY } from "../../src/theme/resolve";

const HEX = (hex: string) => {
  const value = hex.replace("#", "");
  return `${parseInt(value.slice(0, 2), 16)} ${parseInt(value.slice(2, 4), 16)} ${parseInt(
    value.slice(4, 6),
    16,
  )}`;
};

let container: HTMLDivElement;
let root: Root | null = null;

const baseReport = {
  id: "ventas",
  title: "Ventas",
  description: "",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: {},
  periods: { default: "mtd", allowed: ["mtd"] },
  compare: { default: "none", allowed: ["none"] },
  filters: [],
  pdf: false,
  ai_narrative: false,
};

const data = {
  selection: {
    current: { from: "2026-10-01", to: "2026-10-23" },
    previous: null,
    period: "mtd",
    compare: "none",
    filters: {},
  },
  freshness: { updated_at: "2026-10-23T20:00:00Z", mode: "dataset", data_version: "v1" },
  views: [],
  metrics: [],
};

function sharedWith(theme: Record<string, unknown> | undefined) {
  return {
    dashboard: { code: "ventas", name: "Ventas" },
    expires_at: "2026-12-31T00:00:00Z",
    theme: null,
    report: { ...baseReport, layout: theme ? { theme } : {} },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
  localStorage.clear();
  sessionStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-palette");
  vi.mocked(api.get).mockReset();
});

async function renderShared(shared: ReturnType<typeof sharedWith>) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === "/api/shared/tok") return shared;
    if (path.startsWith("/api/shared/tok/data")) return data;
    throw new Error(`unexpected ${path}`);
  });
  await act(async () => {
    root?.render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/s/tok"]}>
          <Routes>
            <Route path="/s/:token" element={<SharedDashboard />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

const area = () => document.querySelector("[data-report-mode]") as HTMLElement | null;

describe("report theme resolution", () => {
  it("prefers the report's theme id, then the deprecated palette, then the installation", () => {
    expect(reportThemeId({ id: "acme-azul" }, "clasico")).toBe("acme-azul");
    expect(reportThemeId({ palette: "contraste" }, "clasico")).toBe("contraste");
    expect(reportThemeId({ id: "acme", palette: "contraste" }, "clasico")).toBe("acme");
    expect(reportThemeId({}, "clasico")).toBe("clasico");
    expect(reportThemeId(null, null)).toBe("impacto");
  });

  it("reads the mode, defaulting to auto", () => {
    expect(reportMode({ mode: "dark" })).toBe("dark");
    expect(reportMode({ mode: "light" })).toBe("light");
    expect(reportMode({ mode: "auto" })).toBe("auto");
    expect(reportMode({ mode: "neon" as string })).toBe("auto");
    expect(reportMode(null)).toBe("auto");
  });

  it("knows the built-ins without the network and finds them by id", () => {
    expect(knownTheme("impacto")).toBe(BUILTIN_THEMES.impacto);
    expect(knownTheme("acme-azul")).toBeNull();
    expect(knownTheme(null)).toBeNull();
  });
});

describe("a report in its own mode", () => {
  it("paints the report area with the declared theme, light tokens and all", async () => {
    await renderShared(sharedWith({ id: "contraste" }));
    const block = area();
    expect(block).toBeTruthy();
    expect(block!.dataset.reportTheme).toBe("contraste");
    expect(block!.dataset.reportMode).toBe("light");
    const surface = deriveTokens(BUILTIN_THEMES.contraste, "light").surface;
    expect(block!.getAttribute("style")).toContain(HEX(surface));
  });

  it("turns the report area dark inside a light application", async () => {
    await renderShared(sharedWith({ id: "contraste", mode: "dark" }));
    expect(area()!.dataset.reportMode).toBe("dark");
    const surface = deriveTokens(BUILTIN_THEMES.contraste, "dark").surface;
    expect(area()!.getAttribute("style")).toContain(HEX(surface));
    // The chrome keeps the light appearance: only the report's area turned.
    expect(document.documentElement.dataset.theme).not.toBe("dark");
    const lightSurface = deriveTokens(BUILTIN_THEMES.contraste, "light").surface;
    expect(area()!.getAttribute("style")).not.toContain(HEX(lightSurface));
  });

  it("opens in the report's mode even when this device prefers the other", async () => {
    localStorage.setItem(STORAGE_KEY, "light");
    await renderShared(sharedWith({ mode: "dark" }));
    expect(area()!.dataset.reportMode).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("follows the application when the report says auto", async () => {
    localStorage.setItem(STORAGE_KEY, "dark");
    await renderShared(sharedWith({ id: "impacto", mode: "auto" }));
    expect(area()!.dataset.reportMode).toBe("dark");
  });
});

describe("the report's theme is the viewer's to override", () => {
  it("keeps the viewer's choice for the session and reports it back", async () => {
    const { writeViewerMode } = await import("../../src/theme/library");
    writeViewerMode("ventas", "dark");
    await renderShared(sharedWith({ id: "impacto", mode: "light" }));
    const block = document.querySelector("[data-report-mode]") as HTMLElement;
    expect(block.dataset.reportMode).toBe("dark");
    expect(sessionStorage.getItem("bizview.report-mode.ventas")).toBe("dark");
  });

  it("falls back to the application's mode when the theme is only a deprecated palette", async () => {
    await renderShared(sharedWith({ palette: "monocromo" }));
    expect(area()!.dataset.reportTheme).toBe("monocromo");
    expect(area()!.dataset.reportMode).toBe("light");
  });

  it("keeps rendering with the installation's look when the theme no longer exists", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/shared/tok") return sharedWith({ id: "borrado" });
      if (path.startsWith("/api/shared/tok/data")) return data;
      if (path === "/api/themes/borrado") throw new Error("404");
      throw new Error(`unexpected ${path}`);
    });
    await act(async () => {
      root?.render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/s/tok"]}>
            <Routes>
              <Route path="/s/:token" element={<SharedDashboard />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>,
      );
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(area()).toBeTruthy();
    const data_ = document.querySelector("[data-report-mode]") as HTMLElement;
    expect(data_.dataset.reportTheme).not.toBe("borrado");
  });

  it("names the toggle in the viewer's language", () => {
    expect(t.reportActions.modeDark).toBeTruthy();
    expect(t.reportActions.modeLight).toBeTruthy();
    expect(t.reportActions.modeDark).not.toBe(t.reportActions.modeLight);
  });
});

describe("the report area", () => {
  it("paints from the theme and the mode it is given, not from the application's", async () => {
    const { ReportArea } = await import("../../src/components/report/ReportArea");
    await act(async () => {
      root?.render(<ReportArea theme={BUILTIN_THEMES.clasico} mode="dark">contenido</ReportArea>);
    });
    const block = area()!;
    expect(block.dataset.reportMode).toBe("dark");
    expect(block.dataset.reportTheme).toBe("clasico");
    const surface = deriveTokens(BUILTIN_THEMES.clasico, "dark").surface;
    expect(block.getAttribute("style")).toContain(`--c-kpi-surface: ${HEX(surface)}`);
    // The shape tokens travel with the theme, so a component never needs a literal.
    expect(block.getAttribute("style")).toContain("--t-radius:");
    expect(block.textContent).toBe("contenido");
  });

  it("switches every colour token when only the mode changes", async () => {
    const { ReportArea } = await import("../../src/components/report/ReportArea");
    await act(async () => {
      root?.render(<ReportArea theme={BUILTIN_THEMES.impacto} mode="light">x</ReportArea>);
    });
    const light = area()!.getAttribute("style");
    await act(async () => {
      root?.render(<ReportArea theme={BUILTIN_THEMES.impacto} mode="dark">x</ReportArea>);
    });
    const dark = area()!.getAttribute("style");
    expect(light).not.toBe(dark);
    expect(dark).toContain(
      `--c-kpi-surface: ${HEX(deriveTokens(BUILTIN_THEMES.impacto, "dark").surface)}`,
    );
    expect(dark).toContain(
      `--c-chart-1: ${HEX(deriveTokens(BUILTIN_THEMES.impacto, "dark").series1)}`,
    );
  });
});
