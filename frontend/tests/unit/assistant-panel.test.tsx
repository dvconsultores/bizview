import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), del: vi.fn() },
  askReauth: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  },
  qs: () => "",
}));
vi.mock("../../src/config/BrandingContext", () => ({ useBranding: () => ({ ai_enabled: true }) }));
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: { is_superuser: true } }),
  useOptionalUser: () => ({ is_superuser: true, role: "admin" }),
}));

import { api } from "../../src/api/client";
import { AssistantPanel } from "../../src/components/assistant/AssistantPanel";
import { AssistantPanelProvider } from "../../src/components/assistant/AssistantPanelContext";
import { AssistantToggle } from "../../src/components/assistant/AssistantToggle";

const ts = "2026-10-03T12:00:00Z";
const base = {
  id: 5, title: "Nueva conversación", status: "open", draft: null, validation: null, preview: null,
  applied_version_id: null, tokens_used: 0, created_at: ts, updated_at: ts,
  messages: [] as unknown[],
};

let container: HTMLElement;
let root: Root;

async function render() {
  await act(async () => {
    root.render(
      <MemoryRouter>
        <AssistantPanelProvider>
          <AssistantToggle />
          <AssistantPanel />
        </AssistantPanelProvider>
      </MemoryRouter>,
    );
  });
}

const toggle = () => container.querySelector<HTMLButtonElement>("#assistant-toggle")!;
const byLabel = (label: string) => container.querySelector<HTMLButtonElement>(`[aria-label="${label}"]`);

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe("assistant panel (Customer A-style, docked)", () => {
  it("is hidden until the top-bar button opens it, with the greeting", async () => {
    await render();
    expect(container.querySelector("#assistant-panel")).toBeNull();
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    await act(async () => toggle().click());
    const panel = container.querySelector("aside#assistant-panel");
    expect(panel).not.toBeNull();
    expect(panel!.textContent).toContain("Hola, soy el asistente de BizView");
    expect(toggle().getAttribute("aria-expanded")).toBe("true");
    expect(api.get).not.toHaveBeenCalled();
  });

  it("asks for the project on the first message, then creates the conversation and remembers it", async () => {
    // Feature 020 (R16): the first message proposes a project (no AI call); creating it opens
    // the conversation inside it and the message is sent.
    vi.mocked(api.get).mockImplementation(async (path: string) =>
      path === "/api/projects" ? { projects: [] } : (undefined as never));
    vi.mocked(api.post).mockImplementation(async (path: string, body?: unknown) => {
      if (path === "/api/assistant/project-proposal") return { name: "Ventas por sucursal", slug: "ventas-por-sucursal" };
      if (path === "/api/projects") return { slug: "ventas-por-sucursal", name: "Ventas por sucursal" };
      if (path === "/api/assistant/sessions") {
        expect(body).toEqual({ project: "ventas-por-sucursal" });
        return { ...base, project: { id: 1, slug: "ventas-por-sucursal", name: "Ventas por sucursal" } };
      }
      return {
        messages: [],
        session: { ...base, messages: [
          { id: 1, role: "user", content: "Hola", created_at: ts },
          { id: 2, role: "assistant", content: "Claro", created_at: ts },
        ] },
      };
    });
    await render();
    await act(async () => toggle().click());
    const textarea = container.querySelector("textarea")!;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(textarea, "Hola");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const send = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Enviar"))!;
    await act(async () => send.click());
    expect(container.textContent).toContain("¿En qué proyecto trabajamos?");
    const nameInput = Array.from(container.querySelectorAll("input")).find(
      (i) => (i as HTMLInputElement).value === "Ventas por sucursal");
    expect(nameInput).toBeDefined();

    const create = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Crear proyecto"))!;
    await act(async () => create.click());
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });

    expect(api.post).toHaveBeenCalledWith("/api/assistant/project-proposal", { text: "Hola" });
    expect(api.post).toHaveBeenCalledWith("/api/projects", { name: "Ventas por sucursal", slug: "ventas-por-sucursal" });
    expect(api.post).toHaveBeenCalledWith("/api/assistant/sessions/5/messages", { text: "Hola" });
    expect(container.textContent).toContain("Claro");
    expect(localStorage.getItem("bizview.assistantPanel.session")).toBe("5");
  });

  it("expands, collapses and closes", async () => {
    await render();
    await act(async () => toggle().click());
    await act(async () => byLabel("Expandir")!.click());
    expect(byLabel("Contraer")).not.toBeNull();
    expect(localStorage.getItem("bizview.assistantPanel.mode")).toBe("expanded");
    await act(async () => byLabel("Contraer")!.click());
    expect(byLabel("Expandir")).not.toBeNull();
    const closeInPanel = container.querySelector<HTMLButtonElement>('#assistant-panel [aria-label="Cerrar asistente"]')!;
    await act(async () => closeInPanel.click());
    expect(container.querySelector("#assistant-panel")).toBeNull();
    expect(localStorage.getItem("bizview.assistantPanel.mode")).toBe("closed");
  });

  it("loads the remembered conversation under StrictMode (effects run twice in development)", async () => {
    localStorage.setItem("bizview.assistantPanel.mode", "docked");
    localStorage.setItem("bizview.assistantPanel.session", "5");
    vi.mocked(api.get).mockResolvedValue({
      ...base, title: "Ventas por marca",
      messages: [{ id: 1, role: "user", content: "Hola de antes", created_at: ts }],
    });
    await act(async () => {
      root.render(
        <StrictMode>
          <MemoryRouter>
            <AssistantPanelProvider>
              <AssistantToggle />
              <AssistantPanel />
            </AssistantPanelProvider>
          </MemoryRouter>
        </StrictMode>,
      );
    });
    expect(container.textContent).toContain("Hola de antes");
    expect(container.querySelector("#assistant-panel h2")?.textContent).toBe("Ventas por marca");
  });
});
