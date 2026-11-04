import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
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
      public details: Record<string, unknown> = {},
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

vi.mock("../../src/components/Toast", () => ({
  useToast: () => vi.fn(),
}));

vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ ai_enabled: aiEnabled }),
  useBrandingRefresh: () => async () => undefined,
}));

import { api } from "../../src/api/client";
import type { DataSource, StructurePack } from "../../src/api/types";
import { SourceStructure } from "../../src/pages/admin/SourceStructure";
import { t } from "../../src/i18n/es";

let aiEnabled = true;
const T = t.admin.sourceStructure;
const CHAT = t.sourceChat;

const source = {
  id: 7, name: "ERP ventas", kind: "postgresql", description: "", enabled: true,
  direct_reports: false, settings: {}, secret_fields: [], imported: false, last_test: null,
  created_at: "", updated_at: "",
} as unknown as DataSource;

const restSource = { ...source, id: 8, name: "coinmarketcap", kind: "rest" } as unknown as DataSource;

const pack: StructurePack = {
  pack: {
    version: 1, source: "ERP ventas", kind: "postgresql", generated_at: "2026-11-03T10:00:00Z",
    timezone: "UTC", bi_ready: false, bi_ready_scopes: [], notes: "Plan free.", truncated: false,
  },
  structure: {
    kind: "postgresql",
    tables: [
      { schema: "ventas", name: "orders", kind: "table", estimated_rows: 1200,
        primary_key: ["id"],
        columns: [
          { name: "id", type: "integer", nullable: false, personal: false },
          { name: "created_at", type: "timestamptz", nullable: false, personal: false,
            range: { min: "2023-01-04", max: "2026-11-02" } },
          { name: "customer_email", type: "text", nullable: true, personal: true },
        ] },
      { schema: "public", name: "clientes", kind: "table", estimated_rows: 30,
        primary_key: [], columns: [{ name: "nombre", type: "text", nullable: true,
                                     personal: true }] },
    ],
  },
};

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  aiEnabled = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

/** React tracks the last value it wrote: a controlled field needs the native setter. */
async function type(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const proto = el instanceof HTMLTextAreaElement
    ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  await flush();
}

async function flush() {
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

async function renderStructure(
  data: StructurePack = pack,
  target: DataSource = source,
  history: { turns: { role: "question" | "answer"; text: string | null; at: string }[] } = { turns: [] },
) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith("/structure")) return data;
    if (path.endsWith("/samples")) return { items: [] };
    if (path.endsWith("/chat")) return { ...history, cap: 100000, spent_today: 1200 };
    throw new Error(`unexpected path ${path}`);
  });
  await act(async () => {
    root?.render(<SourceStructure source={target} />);
  });
  await flush();
}

const text = () => container.textContent ?? "";

describe("Estructura tab", () => {
  it("lists schemas, tables and columns with their types", async () => {
    await renderStructure();
    expect(text()).toContain("ventas");
    expect(text()).toContain("public");
    expect(text()).toContain("orders");
    expect(text()).toContain(T.rows(1200));
    expect(text()).toContain(T.dates("2023-01-04", "2026-11-02"));
    expect(text()).toContain("customer_email");
    expect(text()).toContain(T.personalChip);
  });

  it("filters by table name and by column name", async () => {
    await renderStructure();
    const search = container.querySelector("input")!;
    await type(search, "clientes");
    expect(text()).toContain("clientes");
    expect(text()).not.toContain("orders");
    await type(search, "zzz");
    expect(text()).toContain(T.searchEmpty("zzz"));
  });

  it("offers both downloads pointing at the pack routes", async () => {
    await renderStructure();
    const links = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(links).toContain("/api/sources/ERP%20ventas/structure?format=md");
    expect(links).toContain("/api/sources/ERP%20ventas/structure?format=json");
    expect(text()).toContain(T.downloadMd);
    expect(text()).toContain(T.downloadJson);
  });

  it("toggles a column's personal flag and reloads the pack", async () => {
    await renderStructure();
    const chip = [...container.querySelectorAll("button")]
      .find((b) => b.textContent === T.personalChip
        && b.closest("tr")?.textContent?.includes("customer_email"));
    expect(chip).toBeDefined();
    await act(async () => chip!.click());
    await flush();
    expect(vi.mocked(api.put)).toHaveBeenCalledWith(
      "/api/sources/ERP%20ventas/structure/columns",
      { schema_name: "ventas", table: "orders", column: "customer_email", personal: false },
    );
  });

  it("shows the sample requests of a REST source and adds one", async () => {
    await renderStructure({ ...pack, pack: { ...pack.pack, kind: "rest" },
      structure: { kind: "rest", samples: [] } }, restSource);
    expect(text()).toContain(T.samples);
    expect(text()).toContain(T.restEmpty);
    const inputs = [...container.querySelectorAll("input")];
    await type(inputs[0], "listados");
    await type(inputs[1], "v1/listings");
    const add = [...container.querySelectorAll("button")].find((b) => b.textContent === T.sampleAdd)!;
    expect(add).toBeDefined();
    await act(async () => add.click());
    await flush();
    expect(vi.mocked(api.post)).toHaveBeenCalledWith(
      "/api/sources/coinmarketcap/samples",
      { name: "listados", path: "v1/listings", params: {} },
    );
  });

  it("with AI off the chat explains how to enable it instead of offering an input", async () => {
    aiEnabled = false;
    await renderStructure();
    expect(text()).toContain(CHAT.off);
    const ask = [...container.querySelectorAll("button")].find((b) => b.textContent === CHAT.ask);
    expect(ask?.hasAttribute("disabled")).toBe(true);
  });

  it("shows an answer and chips the objects the pack does not know", async () => {
    vi.mocked(api.post).mockResolvedValue({
      answer: "La tabla `ventas_fantasma` no…", refused: false,
      unknown: [{ name: "ventas_fantasma", kind: "table" }], model: "m",
      usage: { cap: 100000, spent_today: 2000 }, tokens_in: 10, tokens_out: 5,
      created_at: "2026-11-03T10:00:01Z",
    });
    await renderStructure();
    const box = container.querySelector("#structure-chat-question") as HTMLTextAreaElement;
    await type(box, "¿dónde están los pagos?");
    const ask = [...container.querySelectorAll("button")].find((b) => b.textContent === CHAT.ask)!;
    await act(async () => ask.click());
    await flush();
    expect(text()).toContain(CHAT.unknownHelp);
    expect(text()).toContain("ventas_fantasma");
    expect(text()).toContain(CHAT.budget(2000, 100000));
  });

  it("renders the typed provider error with the link to the AI page", async () => {
    const { ApiError } = await import("../../src/api/client");
    vi.mocked(api.post).mockRejectedValue(new ApiError(
      502, "ai_no_credit", "La cuenta del proveedor de IA no tiene saldo.",
      {}, { ai: { code: "no_credit", action: "admin_ai" } }));
    await renderStructure();
    const box = container.querySelector("#structure-chat-question") as HTMLTextAreaElement;
    await type(box, "¿qué tablas hay?");
    const ask = [...container.querySelectorAll("button")].find((b) => b.textContent === CHAT.ask)!;
    await act(async () => ask.click());
    await flush();
    expect(text()).toContain("La cuenta del proveedor de IA no tiene saldo.");
    expect(container.querySelector('a[href="/admin/ia"]')).not.toBeNull();
  });
});
