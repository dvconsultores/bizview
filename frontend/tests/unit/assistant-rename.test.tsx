import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string,
      public fields: Record<string, string> = {}) { super(message); }
  },
  qs: () => "",
}));
vi.mock("../../src/config/BrandingContext", () => ({ useBranding: () => ({ ai_enabled: true }) }));
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: { is_superuser: true } }),
  useOptionalUser: () => ({ is_superuser: true, attachments_notice_at: "2026-01-01T00:00:00Z" }),
}));

import { api, ApiError } from "../../src/api/client";
import { EditableTitle } from "../../src/components/assistant/EditableTitle";
import { AssistantPanel } from "../../src/components/assistant/AssistantPanel";
import { AssistantPanelProvider } from "../../src/components/assistant/AssistantPanelContext";
import { AssistantToggle } from "../../src/components/assistant/AssistantToggle";
import { ViewHost } from "../../src/components/ViewHost";
import { AssistantSession } from "../../src/pages/admin/AssistantSession";

const ts = "2026-10-05T12:00:00Z";
const base = {
  id: 5,
  title: "Ventas por marca",
  status: "open",
  draft: null,
  validation: null,
  preview: null,
  applied_version_id: null,
  tokens_used: 0,
  created_at: ts,
  updated_at: ts,
  messages: [] as unknown[],
};

describe("conversation rename (T047)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const setValue = async (input: HTMLInputElement, value: string) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(input, value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  };

  const keyDown = async (input: HTMLInputElement, key: string) => {
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
    });
  };

  const blur = async (input: HTMLInputElement) => {
    await act(async () => {
      input.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("EditableTitle: pencil opens input, Enter trims and saves once", async () => {
    const onRenamed = vi.fn();
    vi.mocked(api.patch).mockResolvedValue({ ...base, title: "Cierre mensual" });
    await act(async () => {
      root.render(
        <EditableTitle sessionId={5} title="Ventas por marca" onRenamed={onRenamed}>
          <h2>Ventas por marca</h2>
        </EditableTitle>,
      );
    });

    const pencil = container.querySelector<HTMLButtonElement>("[data-rename-trigger]")!;
    await act(async () => {
      pencil.click();
    });

    const input = container.querySelector<HTMLInputElement>('input[type="text"]')!;
    expect(input).not.toBeNull();
    expect(input.value).toBe("Ventas por marca");
    expect(input.maxLength).toBe(120);
    expect(document.activeElement).toBe(input);

    await setValue(input, "  Cierre mensual  ");
    await keyDown(input, "Enter");
    await act(async () => {});

    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/5", { title: "Cierre mensual" });
    expect(onRenamed).toHaveBeenCalledWith(expect.objectContaining({ title: "Cierre mensual" }));
    expect(container.querySelector('input[type="text"]')).toBeNull();

    // Simulate the blur that React would fire after Enter, must not send a second request.
    await blur(input);
    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(container.querySelector("[data-rename-trigger]"));
  });

  it("EditableTitle: Escape cancels without patch and stops propagation", async () => {
    const parentKeyDown = vi.fn();
    const onRenamed = vi.fn();
    await act(async () => {
      root.render(
        <div onKeyDown={parentKeyDown}>
          <EditableTitle sessionId={5} title="Ventas por marca" onRenamed={onRenamed}>
            <h2>Ventas por marca</h2>
          </EditableTitle>
        </div>,
      );
    });

    await act(async () => {
      container.querySelector<HTMLButtonElement>("[data-rename-trigger]")!.click();
    });
    const input = container.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(input, "Otro nombre");
    await keyDown(input, "Escape");

    expect(api.patch).not.toHaveBeenCalled();
    expect(container.querySelector('input[type="text"]')).toBeNull();
    expect(container.querySelector("h2")!.textContent).toBe("Ventas por marca");
    expect(parentKeyDown).not.toHaveBeenCalled();
  });

  it("EditableTitle: blur saves with trimmed title", async () => {
    const onRenamed = vi.fn();
    vi.mocked(api.patch).mockResolvedValue({ ...base, title: "Nombre nuevo" });
    await act(async () => {
      root.render(
        <EditableTitle sessionId={5} title="Ventas por marca" onRenamed={onRenamed}>
          <h2>Ventas por marca</h2>
        </EditableTitle>,
      );
    });

    await act(async () => {
      container.querySelector<HTMLButtonElement>("[data-rename-trigger]")!.click();
    });
    const input = container.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(input, " Nombre nuevo ");
    await blur(input);
    await act(async () => {});

    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/5", { title: "Nombre nuevo" });
    expect(onRenamed).toHaveBeenCalledWith(expect.objectContaining({ title: "Nombre nuevo" }));
    expect(container.querySelector('input[type="text"]')).toBeNull();
  });

  it("EditableTitle: invalid whitespace shows alert, unchanged title sends nothing", async () => {
    await act(async () => {
      root.render(
        <EditableTitle sessionId={5} title="Ventas por marca" onRenamed={vi.fn()}>
          <h2>Ventas por marca</h2>
        </EditableTitle>,
      );
    });

    await act(async () => {
      container.querySelector<HTMLButtonElement>("[data-rename-trigger]")!.click();
    });
    const input = container.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(input, "   ");
    await keyDown(input, "Enter");

    expect(api.patch).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')!.textContent).toBe(
      "El nombre debe tener entre 1 y 120 caracteres.",
    );
    expect(container.querySelector<HTMLInputElement>('input[type="text"]')).not.toBeNull();
    expect(container.querySelector<HTMLInputElement>('input[type="text"]')!.getAttribute("aria-invalid")).toBe("true");

    await setValue(input, "Ventas por marca");
    await keyDown(input, "Enter");
    expect(api.patch).not.toHaveBeenCalled();
    expect(container.querySelector('input[type="text"]')).toBeNull();
  });

  it("EditableTitle: server errors show inline messages and stay editing", async () => {
    vi.mocked(api.patch).mockRejectedValue(new ApiError(422, "validation_error", "El nombre debe tener entre 1 y 120 caracteres."));
    await act(async () => {
      root.render(
        <EditableTitle sessionId={5} title="Ventas por marca" onRenamed={vi.fn()}>
          <h2>Ventas por marca</h2>
        </EditableTitle>,
      );
    });

    await act(async () => {
      container.querySelector<HTMLButtonElement>("[data-rename-trigger]")!.click();
    });
    let input = container.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(input, "Nombre inválido");
    await keyDown(input, "Enter");
    await act(async () => {});

    expect(container.querySelector('[role="alert"]')!.textContent).toBe("El nombre debe tener entre 1 y 120 caracteres.");
    expect(container.querySelector('input[type="text"]')).not.toBeNull();

    vi.mocked(api.patch).mockRejectedValue(new Error("network down"));
    input = container.querySelector<HTMLInputElement>('input[type="text"]')!;
    await keyDown(input, "Enter");
    await act(async () => {});

    expect(container.querySelector('[role="alert"]')!.textContent).toBe("No se pudo renombrar la conversación.");
    expect(container.querySelector('input[type="text"]')).not.toBeNull();
  });

  it("docked panel: header pencil renames and Escape inside input does not close panel", async () => {
    localStorage.setItem("bizview.assistantPanel.mode", "docked");
    localStorage.setItem("bizview.assistantPanel.session", "5");
    vi.mocked(api.get).mockResolvedValue({ ...base });
    vi.mocked(api.patch).mockResolvedValue({ ...base, title: "Cierre mensual" });
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
    await act(async () => {});

    expect(document.querySelector<HTMLElement>("#assistant-panel h2")!.textContent).toBe("Ventas por marca");

    const pencil = document.querySelector<HTMLButtonElement>("#assistant-panel [data-rename-trigger]")!;
    await act(async () => {
      pencil.click();
    });

    const input = document.querySelector<HTMLInputElement>("#assistant-panel input[type='text']")!;
    await setValue(input, "Otro nombre");
    await keyDown(input, "Escape");
    expect(document.querySelector("#assistant-panel")).not.toBeNull();
    expect(document.querySelector("#assistant-panel input[type='text']")).toBeNull();
    expect(document.querySelector<HTMLElement>("#assistant-panel h2")!.textContent).toBe("Ventas por marca");

    await act(async () => {
      document.querySelector<HTMLButtonElement>("#assistant-panel [data-rename-trigger]")!.click();
    });
    const reopenedInput = document.querySelector<HTMLInputElement>("#assistant-panel input[type='text']")!;
    await setValue(reopenedInput, "Cierre mensual");
    await keyDown(reopenedInput, "Enter");
    await act(async () => {});

    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/5", { title: "Cierre mensual" });
    expect(document.querySelector<HTMLElement>("#assistant-panel h2")!.textContent).toBe("Cierre mensual");
  });

  it("docked panel history: rename rows updates popover and panel title", async () => {
    localStorage.setItem("bizview.assistantPanel.mode", "docked");
    localStorage.setItem("bizview.assistantPanel.session", "5");
    vi.mocked(api.get).mockImplementation(async (path: string) =>
      path === "/api/assistant/sessions"
        ? {
            sessions: [
              { id: 5, title: "Ventas por marca", status: "open", updated_at: ts, tokens_used: 0 },
              { id: 6, title: "Inventario", status: "open", updated_at: ts, tokens_used: 0 },
            ],
          }
        : { ...base },
    ) as any;

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
    await act(async () => {});

    await act(async () => {
      document.querySelector<HTMLButtonElement>('button[aria-label="Conversaciones"]')!.click();
    });
    await act(async () => {});

    let popover = document.querySelector<HTMLElement>("#assistant-history-popover")!;
    const rowPencil = popover.querySelector<HTMLButtonElement>('[aria-label="Renombrar Inventario"]')!;
    await act(async () => {
      rowPencil.click();
    });

    const rowInput = popover.querySelector<HTMLInputElement>('input[type="text"]')!;
    await keyDown(rowInput, "Escape");
    expect(document.querySelector("#assistant-history-popover")).not.toBeNull();
    expect(popover.querySelector('input[type="text"]')).toBeNull();

    popover = document.querySelector<HTMLElement>("#assistant-history-popover")!;
    await act(async () => {
      popover.querySelector<HTMLButtonElement>('[aria-label="Renombrar Inventario"]')!.click();
    });
    const reopenedRowInput = popover.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(reopenedRowInput, "Stock");
    vi.mocked(api.patch).mockResolvedValue({ ...base, id: 6, title: "Stock" });
    await keyDown(reopenedRowInput, "Enter");
    await act(async () => {});

    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/6", { title: "Stock" });
    popover = document.querySelector<HTMLElement>("#assistant-history-popover")!;
    expect(popover.textContent).toContain("Stock");
    expect(popover.textContent).not.toContain("Inventario");
    expect(document.querySelector<HTMLElement>("#assistant-panel h2")!.textContent).toBe("Ventas por marca");

    const panelRow = popover.querySelector<HTMLButtonElement>('[aria-label="Renombrar Ventas por marca"]')!;
    await act(async () => {
      panelRow.click();
    });
    const panelInput = popover.querySelector<HTMLInputElement>('input[type="text"]')!;
    await keyDown(panelInput, "Escape");
    expect(document.querySelector("#assistant-history-popover")).not.toBeNull();
    expect(popover.querySelector('input[type="text"]')).toBeNull();

    popover = document.querySelector<HTMLElement>("#assistant-history-popover")!;
    await act(async () => {
      popover.querySelector<HTMLButtonElement>('[aria-label="Renombrar Ventas por marca"]')!.click();
    });
    const reopenedPanelInput = popover.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(reopenedPanelInput, "Ventas 2026");
    vi.mocked(api.patch).mockResolvedValue({ ...base, title: "Ventas 2026" });
    await keyDown(reopenedPanelInput, "Enter");
    await act(async () => {});

    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/5", { title: "Ventas 2026" });
    expect(document.querySelector<HTMLElement>("#assistant-panel h2")!.textContent).toBe("Ventas 2026");
  });

  it("draft page: rename via header pencil updates h1 and breadcrumbs", async () => {
    vi.mocked(api.get).mockResolvedValue({ ...base });
    vi.mocked(api.patch).mockResolvedValue({ ...base, title: "Cierre mensual" });
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/admin/asistente/5"]}>
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

    const h1 = document.querySelector<HTMLHeadingElement>("h1")!;
    expect(h1.textContent).toContain("Borrador: Ventas por marca");

    const pencil = h1.querySelector<HTMLButtonElement>("[data-rename-trigger]")!;
    await act(async () => {
      pencil.click();
    });

    const input = h1.querySelector<HTMLInputElement>('input[type="text"]')!;
    await setValue(input, "Cierre mensual");
    await keyDown(input, "Enter");
    await act(async () => {});

    expect(api.patch).toHaveBeenCalledWith("/api/assistant/sessions/5", { title: "Cierre mensual" });
    expect(document.querySelector("h1")!.textContent).toContain("Borrador: Cierre mensual");
    expect(document.querySelector("nav")!.textContent).toContain("Cierre mensual");
  });
});
