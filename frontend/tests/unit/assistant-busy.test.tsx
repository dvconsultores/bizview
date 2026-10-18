import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { ViewHost } from "../../src/components/ViewHost";
import { AssistantSession } from "../../src/pages/admin/AssistantSession";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";
import { AssistantHistory } from "../../src/components/assistant/AssistantHistory";
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
  token_budget: 100000,
  created_at: ts,
  updated_at: ts,
  busy: false,
  messages: [{ id: 1, role: "user", content: "Crea un reporte de ingresos", created_at: ts }],
};

const busyMsg = "El asistente sigue trabajando en esta conversación; espera a que termine.";

function buttonByText(label: string) {
  return Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === label,
  ) as HTMLButtonElement;
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

describe("AssistantChat busy handling", () => {
  function Harness({ initial }: { initial: any }) {
    const [s, setS] = useState(initial);
    return <AssistantChat session={s} onSession={setS} />;
  }

  it("busy on open disables the composer and polls until done", async () => {
    const busySession = {
      ...base,
      busy: true,
      messages: [...base.messages, { id: 2, role: "assistant", content: "Ronda 1 lista.", created_at: ts }],
    };
    vi.mocked(api.get).mockResolvedValueOnce(busySession).mockResolvedValueOnce({
      ...base,
      busy: false,
      messages: [...base.messages, { id: 2, role: "assistant", content: "Listo.", created_at: ts }],
    });

    await act(async () => {
      root.render(<Harness initial={busySession} />);
    });
    await act(async () => {});

    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(true);
    expect(container.querySelector('[role="status"]:not([data-session-indicator])')?.textContent).toContain("El asistente sigue trabajando…");
    expect(vi.mocked(api.get)).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS);
    });
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/assistant/sessions/7");
    expect(container.textContent).toContain("Ronda 1 lista.");
    expect(textarea.disabled).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS);
    });
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(2);
    expect(textarea.disabled).toBe(false);
    expect(container.querySelector('[role="status"]:not([data-session-indicator])')).toBeNull();
    expect(container.textContent).toContain("Listo.");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS * 3);
    });
    expect(vi.mocked(api.get)).toHaveBeenCalledTimes(2);
  });

  it("409 assistant_busy on send enters busy state", async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError(409, "assistant_busy", busyMsg));
    vi.mocked(api.get).mockResolvedValueOnce({ ...base, busy: false });

    await act(async () => {
      root.render(<Harness initial={{ ...base, busy: false }} />);
    });
    await act(async () => {});

    const textarea = container.querySelector("textarea") as HTMLTextAreaElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(textarea, "Añade más");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const send = buttonByText("Enviar");
    await act(async () => {
      send.click();
    });

    expect(textarea.disabled).toBe(true);
    expect(textarea.value).toBe("Añade más");
    expect(container.querySelector('[role="status"]:not([data-session-indicator])')?.textContent).toContain("El asistente sigue trabajando…");
    expect(container.textContent).not.toContain(busyMsg);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS);
    });
    expect(textarea.disabled).toBe(false);
    expect(container.querySelector('[role="status"]:not([data-session-indicator])')).toBeNull();
  });

  it("polling stops on unmount", async () => {
    const busySession = { ...base, busy: true };
    await act(async () => {
      root.render(<Harness initial={busySession} />);
    });
    await act(async () => {});

    act(() => root.unmount());
    root = createRoot(container);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS * 3);
    });
    expect(vi.mocked(api.get)).not.toHaveBeenCalled();
  });
});

describe("AssistantSession draft page busy handling", () => {
  function renderPage() {
    return act(async () => {
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
  }

  it("busy on open disables actions and re-enables after polling", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ...base, busy: true }).mockResolvedValueOnce({ ...base, busy: false });

    await renderPage();
    await act(async () => {});

    const preview = buttonByText("Vista previa");
    const apply = buttonByText("Aplicar");
    const archive = buttonByText("Archivar");
    expect(preview.disabled).toBe(true);
    expect(apply.disabled).toBe(true);
    expect(archive.disabled).toBe(true);
    expect(container.querySelector('[role="status"]:not([data-session-indicator])')?.textContent).toContain("El asistente sigue trabajando…");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(BUSY_POLL_MS);
    });
    expect(preview.disabled).toBe(false);
    expect(apply.disabled).toBe(false);
    expect(archive.disabled).toBe(false);
    expect(container.querySelector('[role="status"]:not([data-session-indicator])')).toBeNull();
  });

  it("409 on apply enters busy state without an error alert", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ...base, busy: false });
    vi.mocked(api.post).mockRejectedValueOnce(new ApiError(409, "assistant_busy", busyMsg));

    await renderPage();
    await act(async () => {});

    const apply = buttonByText("Aplicar");
    await act(async () => {
      apply.click();
    });

    expect(container.querySelector('[role="status"]:not([data-session-indicator])')?.textContent).toContain("El asistente sigue trabajando…");
    expect(apply.disabled).toBe(true);
    expect(container.textContent).not.toContain(busyMsg);
  });
});

describe("AssistantHistory busy badge", () => {
  it("shows the badge and disables archive for busy rows", async () => {
    const sessions = [
      { id: 1, title: "Abierta", status: "open", updated_at: ts, tokens_used: 0, token_budget: 100000, busy: false },
      { id: 2, title: "Ventas", status: "open", updated_at: ts, tokens_used: 0, token_budget: 100000, busy: true },
    ];
    vi.mocked(api.get).mockResolvedValueOnce({ sessions });

    await act(async () => {
      root.render(<AssistantHistory currentId={1} onSelect={vi.fn()} onNew={vi.fn()} />);
    });
    await act(async () => {});

    const openBtn = container.querySelector('button[aria-label="Conversaciones"]') as HTMLButtonElement;
    await act(async () => {
      openBtn.click();
    });
    await act(async () => {});

    const openRow = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Abierta"))!;
    const busyRow = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes("Ventas"))!;
    expect(openRow.textContent).not.toContain("Trabajando");
    expect(busyRow.textContent).toContain("Trabajando");

    const archiveOpen = container.querySelector('button[aria-label="Archivar Abierta"]') as HTMLButtonElement;
    const archiveBusy = container.querySelector('button[aria-label="Archivar Ventas"]') as HTMLButtonElement;
    expect(archiveOpen.disabled).toBe(false);
    expect(archiveBusy.disabled).toBe(true);
  });
});
