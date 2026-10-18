import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string, public fields: Record<string, string> = {}) { super(message); }
  },
  qs: () => "",
}));

vi.mock("../../src/components/Toast", () => ({
  useToast: () => vi.fn(),
}));

vi.mock("../../src/components/TelegramAdminCard", () => ({
  TelegramAdminCard: () => null,
}));

import { api } from "../../src/api/client";
import { SourceForm } from "../../src/pages/admin/SourceForm";
import { Sources } from "../../src/pages/admin/Sources";
import { Security } from "../../src/pages/admin/Security";

type FieldDef = {
  name: string;
  label: string;
  type: "string" | "integer" | "enum" | "url" | "pem" | "headers";
  required: boolean;
  secret: boolean;
  default?: unknown;
  options: string[];
  help: string;
  min?: number | null;
  max?: number | null;
  show_if: Record<string, string[]>;
};

const types = {
  postgresql: { label: "PostgreSQL", http_allowed: true, fields: [] },
  soap: { label: "SOAP", http_allowed: true, fields: [] },
  rest: { label: "REST", http_allowed: true, fields: [] },
  supabase: { label: "Supabase", http_allowed: true, fields: [] },
} as unknown as Record<"postgresql" | "soap" | "rest" | "supabase", { label: string; http_allowed: boolean; fields: FieldDef[] }>;

const pgSource = {
  id: 7,
  name: "ERP",
  kind: "postgresql",
  description: "",
  enabled: true,
  direct_reports: true,
  settings: {},
  secret_fields: [],
  imported: false,
  last_test: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};

const restSource = { ...pgSource, id: 8, name: "Legacy", kind: "rest", direct_reports: false };

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

function render(initialEntry: string, path: string, element: ReactNode) {
  return act(async () => {
    root?.render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path={path} element={element} />
        </Routes>
      </MemoryRouter>,
    );
  });
}

function renderForm(initialEntry: string) {
  return act(async () => {
    root?.render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/admin/fuentes/nueva" element={<SourceForm />} />
          <Route path="/admin/fuentes/:id" element={<SourceForm />} />
        </Routes>
      </MemoryRouter>,
    );
  });
}

function leafBadgeCount(badgeText: string): number {
  return Array.from(document.querySelectorAll("*"))
    .filter((el) => el.textContent === badgeText && el.children.length === 0).length;
}

describe("source direct reports flag", () => {
  it("shows switch for postgresql create and hides after REST kind", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
      if (path === "/api/sources/types") return types;
      return null;
    });

    await renderForm("/admin/fuentes/nueva");
    await flush();

    const label = t.directSources.flag;
    expect(document.querySelector(`button[role="switch"][aria-label="${label}"]`)).toBeTruthy();

    const restRadio = document.querySelector(`input[type="radio"][value="rest"]`) as HTMLInputElement;
    await act(async () => { restRadio.click(); });
    await flush();

    expect(document.querySelector(`button[role="switch"][aria-label="${label}"]`)).toBeNull();
  });

  it("shows enabled flag on edit and patches direct_reports false", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
      if (path === "/api/sources/types") return types;
      if (path === "/api/sources/7") return pgSource;
      return null;
    });
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ ...pgSource, direct_reports: false });

    await renderForm("/admin/fuentes/7");
    await flush();

    expect(document.body.textContent).toContain("ERP");

    const label = t.directSources.flag;
    const sw = document.querySelector(`button[role="switch"][aria-label="${label}"]`) as HTMLButtonElement;
    expect(sw).toBeTruthy();
    expect(sw.getAttribute("aria-checked")).toBe("true");

    await act(async () => { sw.click(); });
    await flush();
    expect(sw.getAttribute("aria-checked")).toBe("false");

    const save = Array.from(document.querySelectorAll("button")).find((b) => b.textContent?.includes("Guardar")) as HTMLButtonElement;
    expect(save).toBeTruthy();
    expect(save.disabled).toBe(false);
    await act(async () => { save.click(); });
    await flush();

    expect(api.patch).toHaveBeenCalledWith("/api/sources/7", expect.objectContaining({ direct_reports: false }));
  });

  it("hides switch for REST edit", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
      if (path === "/api/sources/types") return types;
      if (path === "/api/sources/8") return restSource;
      return null;
    });

    await renderForm("/admin/fuentes/8");
    await flush();

    expect(document.body.textContent).toContain("Legacy");

    const label = t.directSources.flag;
    expect(document.querySelector(`button[role="switch"][aria-label="${label}"]`)).toBeNull();
  });

  it("shows direct reports badge in Sources list", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
      if (path === "/api/sources") return { items: [pgSource, restSource] };
      if (path === "/api/sources/types") return types;
      return null;
    });

    await render("/admin/fuentes", "/admin/fuentes", <Sources />);
    await flush();

    expect(leafBadgeCount(t.directSources.badge)).toBe(2);
  });

  it("does not show badge when no source has direct reports", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
      if (path === "/api/sources") return { items: [restSource] };
      if (path === "/api/sources/types") return types;
      return null;
    });

    await render("/admin/fuentes", "/admin/fuentes", <Sources />);
    await flush();

    expect(document.body.textContent).toContain("Legacy");
    expect(leafBadgeCount(t.directSources.badge)).toBe(0);
  });

  it("renders direct reads in Security page", async () => {
    const securityPayload = {
      profile: "private",
      profile_source: "auto",
      http_allowed: true,
      checks: [],
      legacy_origin_notice: false,
      legacy_origin_variable_present: false,
      direct_reads: [
        { source: "bi", total: 5, failed: 0 },
        { source: "erp", total: 3, failed: 2 },
      ],
    };
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue(securityPayload);

    await render("/admin/seguridad", "/admin/seguridad", <Security />);
    await flush();

    expect(document.body.textContent).toContain(t.directReads.title);
    expect(document.querySelectorAll("[data-testid=direct-read-row]")).toHaveLength(2);
    expect(document.body.textContent).toContain(t.directReads.bi);
    expect(document.body.textContent).toContain("erp");
    expect(document.body.textContent).toContain(`${t.directReads.failed}: 2`);
  });

  it("renders empty direct reads text", async () => {
    const securityPayload = {
      profile: "private",
      profile_source: "auto",
      http_allowed: true,
      checks: [],
      legacy_origin_notice: false,
      legacy_origin_variable_present: false,
      direct_reads: [],
    };
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue(securityPayload);

    await render("/admin/seguridad", "/admin/seguridad", <Security />);
    await flush();

    expect(document.body.textContent).toContain(t.directReads.empty);
    expect(document.querySelectorAll("[data-testid=direct-read-row]")).toHaveLength(0);
  });
});
