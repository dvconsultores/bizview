import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  askReauth: vi.fn(async () => false),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
      public fields: Record<string, string> = {},
      public retryAfter?: number,
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

import { api } from "../../src/api/client";
import type { DataSource, GeneratedPack, StructureState } from "../../src/api/types";
import { SourceStructure } from "../../src/pages/admin/SourceStructure";
import { t } from "../../src/i18n/es";

const T = t.admin.sourceStructure;

const source = {
  id: 7, name: "coinmarketcap", kind: "rest", description: "", enabled: true,
  direct_reports: false, settings: {}, secret_fields: [], imported: false, last_test: null,
  created_at: "", updated_at: "",
} as unknown as DataSource;

const scan = {
  pack: {
    version: 1, source: "coinmarketcap", kind: "rest" as const,
    generated_at: "2026-11-03T10:00:00Z", timezone: "UTC", bi_ready: false, bi_ready_scopes: [],
    notes: "", truncated: false,
  },
  structure: { kind: "rest" as const, path: "/v1/listings", shape: { data: [] } },
};

const generated: GeneratedPack = {
  source: "coinmarketcap", kind: "rest", generated_at: "2026-11-03T21:00:00Z",
  generator: { mode: "ai", model: "deepseek-chat", version: 1, tokens: 4200 },
  notes: "",
  tables: [
    { id: "v1/listings", path: "v1/cryptocurrency/listings/latest", records: "$.data",
      pagination: { type: "none" }, row_is: "una moneda del top N", key: ["id"],
      date_field: "last_updated",
      fields: [
        { name: "id", path: "$.id", type: "integer", semantic: "identifier" },
        { name: "price_usd", path: "$.quote.USD.price", type: "numeric", semantic: "amount",
          unit: "USD" },
        { name: "owner_email", path: "$.owner_email", type: "text", semantic: "text",
          personal: true },
      ] },
  ],
  relations: [{ from: "v1/listings.id", to: "v1/quotes.coin_id", kind: "one_to_many",
                confidence: "high" }],
  suggested_metrics: [{ id: "altcoin_season_index", from: "v1/listings",
                        formula_words: "porcentaje del top 100 que supera a BTC" }],
  dropped: ["ventas_fantasma (tabla que la fuente no tiene)"],
};

function state(overrides: Partial<StructureState> = {}): StructureState {
  return {
    generated: null, previous: null, scan, scan_error: null,
    ai: { enabled: true, model: "deepseek-chat", ceiling: 150000 },
    ...overrides,
  };
}

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

async function flush() {
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

async function render(data: StructureState) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith("/structure/pack")) return data;
    if (path.endsWith("/samples")) return { items: [] };
    throw new Error(`unexpected path ${path}`);
  });
  await act(async () => {
    root?.render(<SourceStructure source={source} />);
  });
  await flush();
}

const text = () => container.textContent ?? "";
const button = (label: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent === label);
const links = () => [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));

describe("Estructura tab after the convergence", () => {
  it("offers the generator and the two downloads, with no chat anywhere", async () => {
    await render(state());
    expect(button(T.generate)).toBeDefined();
    expect(links()).toContain("/api/sources/coinmarketcap/structure?format=md&mode=pack");
    expect(links()).toContain("/api/sources/coinmarketcap/structure?format=json&mode=pack");
    expect(text()).not.toContain("Chat de estructura");
  });

  it("disables the button and explains how to enable AI when the provider is off", async () => {
    await render(state({ ai: { enabled: false, model: null, ceiling: 150000 } }));
    expect(button(T.generate)?.hasAttribute("disabled")).toBe(true);
    expect(text()).toContain(T.generateOff);
    expect(container.querySelector('a[href="/admin/ia"]')).not.toBeNull();
  });

  it("shows the plain scan before any run", async () => {
    await render(state());
    expect(text()).toContain(T.scanOnly);
    expect(links()).toContain("/api/sources/coinmarketcap/structure?format=md&mode=pack");
  });

  it("renders the generated pack: table, fields, relations, metrics and what was dropped",
     async () => {
    await render(state({ generated }));
    expect(text()).toContain(T.generatedBadge);
    expect(text()).toContain("v1/listings");
    expect(text()).toContain("una moneda del top N");
    expect(text()).toContain("price_usd");
    expect(text()).toContain("$.");
    expect(text()).toContain(T.personalChip);
    expect(text()).toContain(T.relations);
    expect(text()).toContain("one_to_many");
    expect(text()).toContain(T.metrics);
    expect(text()).toContain("altcoin_season_index");
    expect(text()).toContain(T.dropped);
    expect(text()).toContain("ventas_fantasma");
  });

  it("runs the generator and shows what changed against the previous pack", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.endsWith("/structure/pack")) return state({ generated });
      if (path.endsWith("/samples")) return { items: [] };
      throw new Error(`unexpected path ${path}`);
    });
    const previous = { ...generated, tables: [{ ...generated.tables[0], fields: [
      { name: "id", path: "$.id", type: "integer", semantic: "identifier" }] }] };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ pack: generated, usage: { tokens: 4200, chunks: 1,
                                                              incomplete: [] },
                                    markdown: "# x", previous }), { status: 200 }));
    await render(state());
    await act(async () => button(T.generate)!.click());
    await flush();
    expect(fetchSpy).toHaveBeenCalledWith("/api/sources/coinmarketcap/structure/generate",
                                          expect.objectContaining({ method: "POST" }));
    expect(container.querySelector("[data-diff]")).not.toBeNull();
    expect(text()).toContain(T.diffChanged("v1/listings", "price_usd, owner_email"));
    fetchSpy.mockRestore();
  });

  it("reports a typed generator error and keeps the tab usable", async () => {
    const { ApiError } = await import("../../src/api/client");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "ai_no_credit",
                                             message: "La cuenta del proveedor de IA no tiene saldo." } }),
                   { status: 502 }));
    await render(state());
    await act(async () => button(T.generate)!.click());
    await flush();
    expect(text()).toContain("La cuenta del proveedor de IA no tiene saldo.");
    expect(button(T.generate)).toBeDefined();
    expect(ApiError).toBeDefined();
  });

  it("keeps the sample requests of a REST source and its notes", async () => {
    await render(state());
    expect(text()).toContain(T.samples);
    expect(text()).toContain(T.notes);
  });
});
