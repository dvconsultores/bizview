import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { ViewHost } from "../../src/components/ViewHost";
import { AssistantSession } from "../../src/pages/admin/AssistantSession";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";
import { AssistantPanelProvider } from "../../src/components/assistant/AssistantPanelContext";

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
import { groupDraftFiles } from "../../src/pages/admin/AssistantSession";

const ts = "2026-10-01T12:00:00Z";
const session = {
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
    valid: false,
    errors: [
      { entry: "reports/demo", code: "a", message: "Falta la métrica" },
      { entry: "reports/demo", code: "b", message: "Nombre no válido" },
    ],
    warnings: [],
  },
  preview: null,
  applied_version_id: null,
  tokens_used: 120,
  created_at: ts,
  updated_at: ts,
  messages: [
    { id: 1, role: "user", content: "Crea un reporte de ingresos", created_at: ts },
    { id: 2, role: "assistant", content: "Aquí tienes el borrador.", created_at: ts },
    { id: 3, role: "tool", tool_name: "list_sources", content: "Consultó la lista de fuentes.", created_at: ts },
    { id: 4, role: "assistant", content: "", created_at: ts },
  ],
};

describe("AssistantSession", () => {
  let container: HTMLElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    vi.mocked(api.get).mockResolvedValue(session);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  async function render() {
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/admin/asistente/7"]}>
          <AssistantPanelProvider>
          <Routes>
            <Route
              path="/admin/asistente/:id"
              element={
                <ViewHost>
                  <AssistantSession />
                </ViewHost>
              }
            />
          </Routes>
          </AssistantPanelProvider>
        </MemoryRouter>,
      );
    });
    await act(async () => {});
  }

  // The conversation itself is the shared chat (docked panel / phone page).
  async function renderChat() {
    function Harness() {
      const [s, setS] = useState(session as any);
      return <AssistantChat session={s} onSession={setS} />;
    }
    await act(async () => {
      root.render(<Harness />);
    });
  }

  it("chat renders user, assistant and tool summary; an empty assistant message renders nothing", async () => {
    await renderChat();
    const bubbles = Array.from(container.querySelectorAll("*")).filter(
      (el) => el.children.length === 0 && el.textContent === "Aquí tienes el borrador.",
    );
    expect(bubbles).toHaveLength(1);
    expect(container.textContent).toContain("Crea un reporte de ingresos");
    expect(container.textContent).toContain("Consultó la lista de fuentes.");
  });

  it("draft page shows the problem count and both error messages, and no chat", async () => {
    await render();
    expect(container.querySelector("textarea")).toBeNull();
    expect(container.textContent).toContain("Continuar en el chat");
    expect(container.textContent).toContain("2 problemas");
    expect(container.textContent).toContain("Falta la métrica");
    expect(container.textContent).toContain("Nombre no válido");
  });

  it("chat sending appends the returned messages", async () => {
    const newMsg = { id: 9, role: "assistant", content: "He añadido más métricas.", created_at: ts };
    vi.mocked(api.post).mockResolvedValue({
      messages: [newMsg],
      session: { ...session, messages: [...session.messages, newMsg] },
    });
    await renderChat();

    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(textarea, "Añade más");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const send = Array.from(container.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Enviar"),
    )!;
    await act(async () => {
      send.click();
    });
    await act(async () => {});

    expect(container.textContent).toContain("He añadido más métricas.");
    expect(api.post).toHaveBeenCalledWith("/api/assistant/sessions/7/messages", { text: "Añade más" });
  });
});

describe("groupDraftFiles", () => {
  it("groups draft files as the spec's cards, in order, each file once", () => {
    const groups = groupDraftFiles({
      "reports/a/report.yaml": "x",
      "specs/reports/001-a/spec.md": "y",
      "integrations/b/integration.yaml": "z",
      "specs/integrations/001-b/spec.md": "w",
      "README.md": "r",
    });
    expect(groups.map((g) => g.label)).toEqual([
      "Spec de integración", "Integración", "Spec de reporte", "Reporte", "Otros",
    ]);
    expect(groups.map((g) => g.files)).toEqual([
      ["specs/integrations/001-b/spec.md"], ["integrations/b/integration.yaml"],
      ["specs/reports/001-a/spec.md"], ["reports/a/report.yaml"], ["README.md"],
    ]);
  });
});
