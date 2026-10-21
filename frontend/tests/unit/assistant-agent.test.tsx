import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { ViewHost } from "../../src/components/ViewHost";
import { AssistantSession } from "../../src/pages/admin/AssistantSession";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";
import { AssistantPanelProvider } from "../../src/components/assistant/AssistantPanelContext";
import { ProblemList, problemLocation } from "../../src/components/assistant/ProblemList";
import { readinessItems } from "../../src/components/assistant/Readiness";
import type { AssistantSession as AssistantSessionType, AssistantIssue } from "../../src/api/types";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
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
  qs: () => "",
}));

vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ ai_enabled: true }),
}));

import { api } from "../../src/api/client";

const ts = "2026-10-01T12:00:00Z";

function makeSession(overrides: Partial<AssistantSessionType> = {}): AssistantSessionType {
  return {
    id: 7,
    title: "Prueba",
    status: "open",
    draft: {
      files: {
        "reports/demo/report.yaml": "id: demo\n",
        "specs/reports/001-demo/spec.md": "# Demo\n",
      },
      summary: "Borrador demo",
    },
    validation: {
      valid: true,
      errors: [],
      warnings: [],
    },
    preview: null,
    applied_version_id: null,
    tokens_used: 120,
    created_at: ts,
    updated_at: ts,
    messages: [],
    working_state: {},
    readiness: { ready: true, pending: [] },
    stats: {},
    budget_warning: false,
    ...overrides,
  };
}

function buttonByText(container: HTMLElement, text: string): HTMLButtonElement | undefined {
  return Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === text,
  ) as HTMLButtonElement | undefined;
}

async function flush() {
  await act(async () => {});
}

describe("ProblemList", () => {
  let container: HTMLElement;
  let root: Root;
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("renders file#path, message, fix and expected details", async () => {
    const problems: AssistantIssue[] = [
      {
        entry: "page",
        code: "bad",
        message: "Falta el id.",
        file: "reports/a/report.yaml",
        path: "/id",
        fix: "Agrega id: a",
        expected: { id: "string" },
      },
    ];
    await act(async () => {
      root.render(<ProblemList problems={problems} />);
    });
    expect(container.textContent).toContain("reports/a/report.yaml#/id");
    expect(container.textContent).toContain("Falta el id.");
    expect(container.textContent).toContain("Arreglo:");
    expect(container.textContent).toContain("Agrega id: a");
    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details!.querySelector("summary")?.textContent).toContain("Forma esperada");
    expect(details!.textContent).toContain('"id": "string"');
  });

  it("shows #(raíz) for empty path and falls back to entry", async () => {
    const problems: AssistantIssue[] = [
      { entry: "query", code: "bad", message: "Mala consulta.", path: "", file: null },
    ];
    await act(async () => {
      root.render(<ProblemList problems={problems} />);
    });
    expect(container.textContent).toContain("query#(raíz)");
    expect(container.textContent).toContain("Mala consulta.");
  });

  it("renders nothing for empty problems", async () => {
    await act(async () => {
      root.render(<ProblemList problems={[]} />);
    });
    expect(container.querySelector("ul")).toBeNull();
  });

  it("problemLocation unit", () => {
    expect(problemLocation({ entry: "e", code: "c", message: "m", file: "f", path: "/p" })).toBe("f#/p");
    expect(problemLocation({ entry: "e", code: "c", message: "m", file: null, path: "" })).toBe("e#(raíz)");
    expect(problemLocation({ entry: "e", code: "c", message: "m", file: null, path: null })).toBe("e");
  });
});

describe("readinessItems", () => {
  it("no draft → all three not ok", () => {
    const s = makeSession({ draft: null, readiness: { ready: false, pending: [] } });
    const { items, other, ready } = readinessItems(s);
    expect(items.every((i) => i.ok === false)).toBe(true);
    expect(other).toEqual([]);
    expect(ready).toBe(false);
  });

  it("maps query_check and preview pending; other codes land in other; draft excluded", () => {
    const s = makeSession({
      readiness: {
        ready: false,
        pending: [
          { code: "query_check", file: "reports/a/report.yaml", message: "Consulta sin probar." },
          { code: "preview", file: "reports/b/report.yaml", message: "Sin vista previa." },
          { code: "primary_key", file: "integrations/x.yaml", message: "Falta PK." },
          { code: "draft", file: null, message: "Borrador incompleto." },
        ],
      },
    });
    const { items, other } = readinessItems(s);
    const queries = items.find((i) => i.key === "queries");
    const preview = items.find((i) => i.key === "preview");
    expect(queries?.ok).toBe(false);
    expect(queries?.messages).toEqual(["reports/a/report.yaml: Consulta sin probar."]);
    expect(preview?.ok).toBe(false);
    expect(preview?.messages).toEqual(["reports/b/report.yaml: Sin vista previa."]);
    expect(other).toHaveLength(1);
    expect(other[0].code).toBe("primary_key");
  });

  it("ready mirrors readiness.ready", () => {
    expect(readinessItems(makeSession({ readiness: { ready: true, pending: [] } })).ready).toBe(true);
    expect(readinessItems(makeSession({ readiness: { ready: false, pending: [] } })).ready).toBe(false);
  });
});

describe("AssistantSession draft page", () => {
  let container: HTMLElement;
  let root: Root;
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    vi.mocked(api.get).mockResolvedValue(makeSession());
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  async function renderPage(session: AssistantSessionType) {
    vi.mocked(api.get).mockResolvedValue(session);
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/admin/asistente/7"]}>
          <AssistantPanelProvider>
            <Routes>
              <Route path="/admin/asistente/:id" element={<ViewHost><AssistantSession /></ViewHost>} />
            </Routes>
          </AssistantPanelProvider>
        </MemoryRouter>,
      );
    });
    await flush();
  }

  it("disables Aplicar when not ready, shows pill and blocked hint", async () => {
    const s = makeSession({
      validation: { valid: true, errors: [], warnings: [] },
      readiness: {
        ready: false,
        pending: [{ code: "query_check", file: "reports/a/report.yaml", message: "Consulta sin probar." }],
      },
    });
    await renderPage(s);
    const apply = buttonByText(container, "Aplicar");
    expect(apply?.disabled).toBe(true);
    expect(container.textContent).toContain("Aún no está listo");
    expect(container.textContent).toContain("Consultas comprobadas");
    const items = Array.from(container.querySelectorAll("li[data-ok]"));
    const queryItem = items.find((el) => el.textContent?.includes("Consultas comprobadas"));
    const validationItem = items.find((el) => el.textContent?.includes("Validación"));
    expect(queryItem).not.toBeUndefined();
    expect(queryItem!.getAttribute("data-ok")).toBe("false");
    expect(validationItem).not.toBeUndefined();
    expect(validationItem!.getAttribute("data-ok")).toBe("true");
    expect(queryItem!.textContent).toContain("reports/a/report.yaml: Consulta sin probar.");
    expect(container.textContent).toContain("«Aplicar» se habilita cuando el borrador está listo para aplicar.");
  });

  it("enables Aplicar when ready, pill reads ready", async () => {
    const s = makeSession({ readiness: { ready: true, pending: [] } });
    await renderPage(s);
    const apply = buttonByText(container, "Aplicar");
    expect(apply?.disabled).toBe(false);
    expect(container.textContent).toContain("Listo para aplicar");
  });

  it("renders problem file/path/fix in the draft card", async () => {
    const s = makeSession({
      validation: {
        valid: false,
        errors: [
          {
            entry: "page",
            code: "bad",
            message: "Falta el id.",
            file: "reports/a/report.yaml",
            path: "/id",
            fix: "Agrega id: a",
          },
        ],
        warnings: [],
      },
      readiness: { ready: false, pending: [] },
    });
    await renderPage(s);
    expect(container.textContent).toContain("reports/a/report.yaml#/id");
    expect(container.textContent).toContain("Falta el id.");
    expect(container.textContent).toContain("Agrega id: a");
  });

  it("shows warnings with warning tone", async () => {
    const s = makeSession({
      validation: {
        valid: true,
        errors: [],
        warnings: [{ entry: "w", code: "warn", message: "Un aviso.", file: null, path: null }],
      },
    });
    await renderPage(s);
    expect(container.textContent).toContain("Un aviso.");
  });
});

describe("No budget in the composer (feature 028 revision, unlimited AI)", () => {
  let container: HTMLElement;
  let root: Root;
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  async function renderChat(session: AssistantSessionType) {
    function Harness() {
      const [s, setS] = useState<AssistantSessionType>(session);
      return <AssistantChat session={s} onSession={setS} />;
    }
    await act(async () => {
      root.render(<Harness />);
    });
    await flush();
  }

  it("never shows a budget notice, however many tokens were spent", async () => {
    await renderChat(makeSession({ tokens_used: 9_000_000 }));

    expect(container.querySelector("[data-budget-notice]")).toBeNull();
    expect(container.textContent).not.toContain("presupuesto");
    expect(buttonByText(container, "Ampliar presupuesto")).toBeUndefined();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("Tool chips", () => {
  let container: HTMLElement;
  let root: Root;
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function renderChat(messages: AssistantSessionType["messages"]) {
    const s = makeSession({ messages });
    function Harness() {
      const [session, setSession] = useState<AssistantSessionType>(s);
      return <AssistantChat session={session} onSession={setSession} />;
    }
    await act(async () => {
      root.render(<Harness />);
    });
    await flush();
  }

  it("renders tool chip with data-tool, title and content", async () => {
    await renderChat([
      { id: 1, role: "tool", tool_name: "run_preview", content: "Ejecutó una vista previa (correcta).", created_at: ts },
    ]);
    const chip = container.querySelector('[data-tool="run_preview"]');
    expect(chip).not.toBeNull();
    // The row clamps to one line, so the tooltip carries the full text.
    expect(chip!.getAttribute("title")).toBe("Ejecutó una vista previa (correcta).");
    expect(chip!.textContent).toContain("Ejecutó una vista previa (correcta).");
  });

  it("falls back to label for empty content", async () => {
    await renderChat([{ id: 2, role: "tool", tool_name: "update_notes", content: "", created_at: ts }]);
    const chip = container.querySelector('[data-tool="update_notes"]');
    expect(chip).not.toBeNull();
    expect(chip!.textContent).toContain("Notas de trabajo");
  });

  it("unknown tool gets generic title", async () => {
    await renderChat([{ id: 3, role: "tool", tool_name: "mystery", content: "Hizo algo.", created_at: ts }]);
    const chip = container.querySelector('[data-tool="mystery"]');
    expect(chip).not.toBeNull();
    expect(chip!.getAttribute("title")).toBe("Hizo algo.");
  });
});

describe("Working notes on draft page", () => {
  let container: HTMLElement;
  let root: Root;
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  async function renderPage(session: AssistantSessionType) {
    vi.mocked(api.get).mockResolvedValue(session);
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/admin/asistente/7"]}>
          <AssistantPanelProvider>
            <Routes>
              <Route path="/admin/asistente/:id" element={<ViewHost><AssistantSession /></ViewHost>} />
            </Routes>
          </AssistantPanelProvider>
        </MemoryRouter>,
      );
    });
    await flush();
  }

  it("renders goal/next/decisions/inspected/personal/stats", async () => {
    const s = makeSession({
      working_state: {
        goal: "Crear reporte de ventas.",
        next: "Probar la consulta.",
        decisions: ["Usar tabla public.ventas"],
        inspected: {
          pg: { "public.ventas": "note" },
        },
        personal: {
          pg: { email: "email" },
        },
      },
      stats: { rounds: 4, validations: 2, probes: 1, previews: 3, query_checks: 2 },
    });
    await renderPage(s);
    expect(container.textContent).toContain("Objetivo");
    expect(container.textContent).toContain("Crear reporte de ventas.");
    expect(container.textContent).toContain("Siguiente");
    expect(container.textContent).toContain("Probar la consulta.");
    expect(container.textContent).toContain("Decisiones");
    expect(container.textContent).toContain("Usar tabla public.ventas");
    expect(container.textContent).toContain("Fuentes consultadas");
    expect(container.textContent).toContain("public.ventas — note");
    expect(container.textContent).toContain("Columnas con datos personales");
    expect(container.textContent).toContain("email (correo)");
    expect(container.textContent).toContain("Actividad");
    expect(container.textContent).toContain("Rondas: 4");
  });

  it("shows empty note when no working state", async () => {
    const s = makeSession({ working_state: {}, stats: {} });
    await renderPage(s);
    expect(container.textContent).toContain("El asistente aún no guardó notas de trabajo.");
  });

  it("does not render malformed values", async () => {
    const s = makeSession({
      working_state: {
        goal: 5 as any,
        inspected: { pg: "x" } as any,
        personal: "bad" as any,
      },
      stats: {},
    });
    await renderPage(s);
    expect(container.textContent).toContain("El asistente aún no guardó notas de trabajo.");
    expect(container.textContent).not.toContain("Objetivo");
  });
});

describe("Preview PDF buttons", () => {
  let container: HTMLElement;
  let root: Root;
  const originalFetch = globalThis.fetch;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
    globalThis.fetch = originalFetch;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  });

  async function renderPage(session: AssistantSessionType) {
    vi.mocked(api.get).mockResolvedValue(session);
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/admin/asistente/7"]}>
          <AssistantPanelProvider>
            <Routes>
              <Route path="/admin/asistente/:id" element={<ViewHost><AssistantSession /></ViewHost>} />
            </Routes>
          </AssistantPanelProvider>
        </MemoryRouter>,
      );
    });
    await flush();
  }

  it("shows PDF button only for reports without pdf pending and downloads", async () => {
    const s = makeSession({
      draft: {
        files: {
          "reports/a/report.yaml": "id: a\n",
          "reports/b/report.yaml": "id: b\n",
        },
        summary: "Dos reportes",
      },
      preview: { status: "succeeded", integrations: {} },
      readiness: {
        ready: false,
        pending: [
          { code: "pdf", file: "reports/b/report.yaml", message: "Sin PDF." },
        ],
      },
    });
    await renderPage(s);
    const pdfA = buttonByText(container, "PDF de vista previa: a");
    const pdfB = buttonByText(container, "PDF de vista previa: b");
    expect(pdfA).not.toBeUndefined();
    expect(pdfB).toBeUndefined();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => new Blob(["%PDF"]),
      json: async () => ({}),
    });
    globalThis.fetch = fetchMock as any;
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    await act(async () => {
      pdfA!.click();
    });
    await flush();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/assistant/sessions/7/preview/report/a/pdf",
      expect.objectContaining({
        method: "POST",
        headers: { "X-Requested-With": "fetch" },
      }),
    );
  });

  it("shows server error when PDF download fails", async () => {
    const s = makeSession({
      draft: {
        files: {
          "reports/a/report.yaml": "id: a\n",
        },
        summary: "Un reporte",
      },
      preview: { status: "succeeded", integrations: {} },
      readiness: { ready: false, pending: [] },
    });
    await renderPage(s);
    const pdfA = buttonByText(container, "PDF de vista previa: a");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: "not_found", message: "Este reporte no permite PDF." } }),
    });
    globalThis.fetch = fetchMock as any;
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    await act(async () => {
      pdfA!.click();
    });
    await flush();
    expect(container.textContent).toContain("Este reporte no permite PDF.");
  });
});
