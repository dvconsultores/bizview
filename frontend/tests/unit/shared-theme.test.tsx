/** Feature 030 (US4, FR-006, contracts/share-theme.md): the shared view gets a Claro/Oscuro toggle
 * beside the language toggle, the sharer's first-load theme applies only when this browser has no
 * stored preference, and hostile storage never breaks the page. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string, public fields: Record<string, string> = {}) {
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
import { ThemeSwitcher } from "../../src/components/ThemeSwitcher";
import { ThemeProvider } from "../../src/theme/ThemeContext";
import { STORAGE_KEY } from "../../src/theme/resolve";
import { t } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root | null = null;

const shared = {
  dashboard: { code: "ventas", name: "Ventas" },
  expires_at: "2026-12-31T00:00:00Z",
  theme: "dark" as const,
  report: {
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
  },
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

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === "/api/shared/tok") return shared;
    if (path.startsWith("/api/shared/tok/data")) return data;
    throw new Error(`unexpected ${path}`);
  });
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.unstubAllGlobals();
});

async function renderShared() {
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

const toggle = () =>
  document.querySelector(`[role="radiogroup"][aria-label="${t.theme.label}"]`) as HTMLElement | null;

describe("shared view theme", () => {
  it("shows a two-option toggle beside the language toggle", async () => {
    await renderShared();
    const group = toggle();
    expect(group).toBeTruthy();
    expect(group!.querySelectorAll('[role="radio"]')).toHaveLength(2);
    expect(group!.className).toContain("grid-cols-2");
  });

  it("applies the sharer's theme on the first load when this browser has no preference", async () => {
    await renderShared();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("keeps the viewer's stored choice over the sharer's theme", async () => {
    localStorage.setItem(STORAGE_KEY, "light");
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/shared/tok") return shared;
      if (path.startsWith("/api/shared/tok/data")) return data;
      throw new Error(`unexpected ${path}`);
    });
    await renderShared();
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
  });

  it("switches theme without a reload and persists it", async () => {
    await renderShared();
    const light = Array.from(document.querySelectorAll('[role="radio"]')).find(
      (el) => el.getAttribute("aria-label") === t.theme.light,
    ) as HTMLButtonElement;
    await act(async () => light.click());
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
    expect(vi.mocked(api.patch)).not.toHaveBeenCalled(); // a viewer is nobody's account
  });

  it("survives a blocked localStorage", async () => {
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {},
      clear: () => {},
      key: () => null,
      length: 0,
    } as unknown as Storage;
    vi.stubGlobal("localStorage", blocked);
    await renderShared();
    expect(document.documentElement.dataset.theme).toBe("dark"); // the link still applies
    expect(document.body.textContent).toContain(shared.dashboard.name);
  });
});

describe("ThemeSwitcher compact", () => {
  it("shows the resolved theme as checked and has accessible names", async () => {
    document.documentElement.dataset.theme = "light";
    await act(async () => {
      root?.render(
        <ThemeProvider>
          <ThemeSwitcher compact />
        </ThemeProvider>,
      );
    });
    const radios = Array.from(document.querySelectorAll('[role="radio"]'));
    expect(radios).toHaveLength(2);
    expect(radios.map((el) => el.getAttribute("aria-label"))).toEqual([t.theme.light, t.theme.dark]);
    expect(radios[0].getAttribute("aria-checked")).toBe("true");
  });
});
