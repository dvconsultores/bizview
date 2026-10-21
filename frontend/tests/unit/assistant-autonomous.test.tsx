import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { ViewHost } from "../../src/components/ViewHost";
import { AssistantSession } from "../../src/pages/admin/AssistantSession";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";
import { AssistantPanelProvider } from "../../src/components/assistant/AssistantPanelContext";
import { BUSY_POLL_MS } from "../../src/components/assistant/useAssistantBusy";

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
vi.mock("../../src/config/BrandingContext", () => ({ useBranding: () => ({ ai_enabled: true }) }));

import { api, ApiError } from "../../src/api/client";

const ts = "2026-10-05T12:00:00Z";
const base = {
  id: 7,
  title: "Prueba",
  status: "open",
  draft: { files: { "reports/demo/report.yaml": "id: demo\n" }, summary: "Borrador demo" },
  validation: { valid: true, errors: [], warnings: [] },
  readiness: { ready: true, pending: [] },
  preview: null,
  applied_version_id: null,
  tokens_used: 120,
  created_at: ts,
  updated_at: ts,
  busy: false,
  messages: [{ id: 1, role: "user", content: "Crea un reporte de ingresos", created_at: ts }],
};

function buttonByText(label: string) {
  return Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === label,
  ) as HTMLButtonElement;
}

function stoppedNote() {
  return Array.from(container.querySelectorAll('p[role="status"]')).find(
    (p) => p.textContent === "Detenido.",
  );
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.useFakeTimers();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(api.get).mockReset();
  vi.mocked(api.post).mockReset();
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.useRealTimers();
});

// chat harness
function Harness({ initial }: { initial: any }) {
  const [s, setS] = useState(initial);
  return <AssistantChat session={s} onSession={setS} />;
}

async function typeInComposer(raw: string) {
  const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  await act(async () => {
    setter.call(textarea, raw);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function renderChat(initial: any) {
  await act(async () => {
    root.render(<Harness initial={initial} />);
  });
}

async function renderDraftPage() {
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

const busyStatusSelector = '[role="status"]:not([data-session-indicator])';

describe("autonomous runs (T043)", () => {
  it("send returns 202 → busy → polls → done", async () => {
    await renderChat(base);
    vi.mocked(api.post).mockResolvedValue({
      messages: [{ id: 2, role: "user", content: "Añade el IVA", created_at: ts }],
      session: {
        ...base,
        busy: true,
        messages: [...base.messages, { id: 2, role: "user", content: "Añade el IVA", created_at: ts }],
      },
    });
    await typeInComposer("Añade el IVA");
    await act(async () => buttonByText("Enviar")?.click());
    await act(async () => {});

    expect(api.post).toHaveBeenCalledWith("/api/assistant/sessions/7/messages", { text: "Añade el IVA" });
    expect(container.textContent).toContain("Añade el IVA");
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(true);
    const busyLine = container.querySelector(busyStatusSelector);
    expect(busyLine?.textContent).toContain("El asistente sigue trabajando…");
    expect(buttonByText("Detener")).toBeTruthy();
    expect(api.get).not.toHaveBeenCalled();

    vi.mocked(api.get).mockResolvedValue({
      ...base,
      busy: false,
      messages: [
        ...base.messages,
        { id: 2, role: "user", content: "Añade el IVA", created_at: ts },
        { id: 3, role: "assistant", content: "Listo, añadí el IVA.", created_at: ts },
      ],
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS);
    });
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(api.get).toHaveBeenCalledWith("/api/assistant/sessions/7");
    expect(container.textContent).toContain("Listo, añadí el IVA.");
    expect(textarea.disabled).toBe(false);
    expect(buttonByText("Detener")).toBeUndefined();
    expect(container.querySelector(busyStatusSelector)).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3 * BUSY_POLL_MS);
    });
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it("Detener stops the run", async () => {
    await renderChat({ ...base, busy: true });
    vi.mocked(api.post).mockResolvedValue({
      ...base,
      busy: false,
      messages: [
        ...base.messages,
        { id: 4, role: "assistant", content: "Detenido por el usuario.", created_at: ts },
      ],
    });
    await act(async () => buttonByText("Detener")?.click());
    await act(async () => {});

    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith("/api/assistant/sessions/7/stop");
    expect(container.textContent).toContain("Detenido por el usuario.");
    expect(stoppedNote()).toBeTruthy();
    expect(container.textContent).not.toContain("El asistente sigue trabajando…");
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(false);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3 * BUSY_POLL_MS);
    });
    expect(api.get).not.toHaveBeenCalled();
  });

  it("Detener on 409 not_running just refreshes", async () => {
    await renderChat({ ...base, busy: true });
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, "not_running", "La conversación no está trabajando."),
    );
    vi.mocked(api.get).mockResolvedValue({ ...base, busy: false });
    await act(async () => buttonByText("Detener")?.click());
    await act(async () => {});

    expect(api.get).toHaveBeenCalledWith("/api/assistant/sessions/7");
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(false);
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it("409 assistant_capacity shows an inline notice", async () => {
    await renderChat(base);
    vi.mocked(api.post).mockRejectedValue(new ApiError(409, "assistant_capacity", "x"));
    await typeInComposer("Hola");
    await act(async () => buttonByText("Enviar")?.click());
    await act(async () => {});

    expect(container.textContent).toContain(
      "Hay demasiadas conversaciones trabajando; intenta en un momento.",
    );
    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(false);
    expect(textarea.value).toBe("Hola");
    expect(buttonByText("Detener")).toBeUndefined();
  });

  it("Detener on the draft page", async () => {
    vi.mocked(api.get).mockResolvedValue({ ...base, busy: true });
    await renderDraftPage();
    const aplicar = buttonByText("Aplicar");
    expect(aplicar.disabled).toBe(true);
    vi.mocked(api.post).mockResolvedValue({ ...base, busy: false });
    await act(async () => buttonByText("Detener")?.click());
    await act(async () => {});
    expect(api.post).toHaveBeenCalledWith("/api/assistant/sessions/7/stop");
    expect(buttonByText("Aplicar").disabled).toBe(false);
    expect(stoppedNote()).toBeTruthy();
  });

  it("has no budget at all: no notice, no button, no /budget call (owner: unlimited AI)", async () => {
    await renderChat({ ...base, tokens_used: 9_000_000 });

    expect(buttonByText("Ampliar presupuesto")).toBeUndefined();
    expect(container.textContent).not.toContain("presupuesto");
    expect(container.textContent).not.toContain("AI_CHAT_BUDGET_MAX");
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("larger chat text (T041)", () => {
  it("bubbles, tools and composer use the larger step", async () => {
    await renderChat({
      ...base,
      messages: [
        ...base.messages,
        {
          id: 5,
          role: "tool",
          tool_name: "list_sources",
          content: "Consultó la lista de fuentes.",
          created_at: ts,
        },
        { id: 6, role: "assistant", content: "Hola", created_at: ts },
      ],
    });
    const userP = Array.from(container.querySelectorAll("p")).find(
      (p) => p.textContent === "Crea un reporte de ingresos",
    )!;
    expect(userP.classList.contains("text-base")).toBe(true);
    expect(userP.classList.contains("leading-relaxed")).toBe(true);
    const assistantP = Array.from(container.querySelectorAll("p")).find((p) => p.textContent === "Hola")!;
    expect(assistantP.classList.contains("text-base")).toBe(true);
    const tool = container.querySelector('span[data-tool="list_sources"]')!;
    expect(tool.classList.contains("text-sm")).toBe(true);
    expect(tool.classList.contains("text-xs")).toBe(false);
    const textarea = container.querySelector("textarea")!;
    expect(textarea.classList.contains("text-base")).toBe(true);
  });
});
