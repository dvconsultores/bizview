import { act, StrictMode, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  },
  qs: () => "",
}));
vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ ai_enabled: true }),
}));
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: { is_superuser: true } }),
  useOptionalUser: () => ({ is_superuser: true }),
}));

import { api, ApiError } from "../../src/api/client";
import { AssistantPanel } from "../../src/components/assistant/AssistantPanel";
import { AssistantPanelProvider } from "../../src/components/assistant/AssistantPanelContext";
import { AssistantToggle } from "../../src/components/assistant/AssistantToggle";
import {
  ACTIVITY_POLL_MS,
  AgentMapOverlay,
  formatDuration,
  formatTokens,
  runElapsedMs,
} from "../../src/components/assistant/AgentMap";
import { ViewHost } from "../../src/components/ViewHost";
import { AssistantSession } from "../../src/pages/admin/AssistantSession";

const ts = "2026-10-03T12:00:00Z";
const base = {
  id: 5,
  title: "Nueva conversación",
  status: "open",
  draft: null,
  validation: null,
  preview: null,
  applied_version_id: null,
  tokens_used: 0,
  token_budget: 10000,
  created_at: ts,
  updated_at: ts,
  messages: [] as unknown[],
};
let container: HTMLElement;
let root: Root;
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
  vi.useRealTimers();
});

const activityUrl = (id: number) => `/api/assistant/sessions/${id}/activity`;
const sessionUrl = (id: number) => `/api/assistant/sessions/${id}`;
function sessionResponse(overrides: Record<string, unknown> = {}) {
  return { ...base, ...overrides } as any;
}
function activityResponse(overrides: Record<string, unknown> = {}) {
  return {
    busy: false,
    model: "gpt-test",
    run: null,
    rounds: [],
    background: [],
    runs: [],
    ...overrides,
  } as any;
}
async function flush() {
  await act(async () => {});
}
const activityCalls = (id: number) =>
  (api.get as any).mock.calls.filter(([url]: [string]) => url === activityUrl(id))
    .length;
const click = (el: Element) =>
  act(() => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
const esc = (target: EventTarget = document.body) =>
  act(() => {
    target.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
  });

describe("formatDuration/formatTokens/runElapsedMs", () => {
  it("formats durations", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
    expect(formatDuration(-1)).toBe("—");
    expect(formatDuration(450)).toBe("450 ms");
    expect(formatDuration(1500)).toBe("1,5 s");
    expect(formatDuration(125000)).toBe("2 min 5 s");
  });

  it("formats tokens", () => {
    expect(formatTokens(999)).toBe("999");
    expect(formatTokens(1234)).toBe("1.234");
    expect(formatTokens(1234567)).toBe("1.234.567");
  });

  it("computes run elapsed ms safely", () => {
    expect(
      runElapsedMs({ started_at: "bad", finished_at: null }, 10),
    ).toBeNull();
    expect(runElapsedMs({ started_at: ts, finished_at: "bad" }, 10)).toBeNull();
    expect(
      runElapsedMs(
        { started_at: ts, finished_at: "2026-10-03T12:00:05Z" },
        10,
      ),
    ).toBe(5000);
    expect(
      runElapsedMs(
        { started_at: ts, finished_at: null },
        Date.parse("2026-10-03T12:00:10Z"),
      ),
    ).toBe(10000);
    expect(
      runElapsedMs(
        { started_at: ts, finished_at: "2026-10-03T11:59:00Z" },
        10,
      ),
    ).toBeNull();
  });
});

describe("AgentMapOverlay", () => {
  it("renders a running activity as a non-modal region with round/flattened tools", async () => {
    const onClose = vi.fn();
    (api.get as any).mockImplementation((url: string) => {
      if (url === activityUrl(9)) {
        return Promise.resolve(
          activityResponse({
            busy: true,
            model: "gpt-test",
            run: {
              id: 3,
              started_at: "2026-10-03T11:59:55Z",
              finished_at: null,
              status: "running",
              round: 2,
              tokens: 12345,
              tools: 3,
              current: { tool: "check", label: "Comprobar reports/x", since: ts },
            },
            rounds: [
              {
                n: 1,
                tools: [
                  {
                    name: "a",
                    label: "Lista de fuentes",
                    status: "ok",
                    started_at: ts,
                    ms: 1500,
                  },
                  { name: "b", label: "Estructura", status: "error", started_at: ts, ms: 900 },
                ],
              },
              {
                n: 2,
                tools: [
                  { name: "c", label: "Vista previa", status: "running", started_at: ts, ms: 3000 },
                ],
              },
            ],
            background: [{ kind: "preview", status: "running", since: "2026-10-03T12:00:01Z" }],
            runs: [
              {
                id: 1,
                started_at: ts,
                finished_at: "2026-10-03T11:00:00Z",
                status: "done",
                rounds: 2,
                tokens: 100,
                tools: 2,
              },
              {
                id: 2,
                started_at: ts,
                finished_at: "2026-10-03T11:30:00Z",
                status: "error",
                rounds: 1,
                tokens: 50,
                tools: 1,
              },
              {
                id: 3,
                started_at: ts,
                finished_at: null,
                status: "running",
                rounds: 3,
                tokens: 200,
                tools: 4,
              },
            ],
          }),
        );
      }
      return Promise.resolve(activityResponse());
    });

    await act(async () => {
      root.render(<AgentMapOverlay sessionId={9} title="Facturas" onClose={onClose} />);
    });
    await flush();

    const map = container.querySelector("[data-agent-map]");
    expect(map).not.toBeNull();
    expect(map!.getAttribute("role")).toBe("region");
    expect(map!.getAttribute("aria-label")).toBe("Mapa del agente");
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(container.querySelector("[aria-modal]")).toBeNull();

    expect(map!.querySelector("h2")!.textContent).toBe("Mapa del agente");
    expect(
      map!.querySelector("[data-agent-map-subtitle]")!.textContent,
    ).toBe("3 herramientas · pulsa un nodo para ver detalles");

    const agentNode = map!.querySelector("[data-agent-node]")!;
    expect(agentNode.textContent).toContain("Facturas");
    expect(agentNode.textContent).toContain("gpt-test · 12.345 tokens");
    expect(agentNode.textContent).toContain("Trabajando");
    expect(agentNode.textContent).toContain("Ahora: Comprobar reports/x");

    const toolNodes = map!.querySelectorAll("[data-tool-node]");
    expect(toolNodes).toHaveLength(3);
    const statuses = Array.from(toolNodes).map((n) =>
      n.getAttribute("data-tool-status"),
    );
    expect(statuses).toEqual(expect.arrayContaining(["ok", "error", "running"]));
    expect(map!.textContent).toContain("1,5 s · ronda 1");
    expect(map!.textContent).toContain("ronda 2");
    expect(map!.querySelector('[class*="motion-safe:animate-ping"]')).not.toBeNull();

    expect(map!.textContent).toContain("1 tarea en segundo plano");
    const bgNode = map!.querySelector("[data-background-node]")!;
    expect(bgNode.textContent).toContain("Vista previa");
    expect(bgNode.textContent).toContain("En curso");

    const details = map!.querySelector("[data-agent-runs]")!;
    expect(details.tagName).toBe("DETAILS");
    expect(details.textContent).toContain("Ejecuciones anteriores (2)");
    const runTexts = Array.from(details.querySelectorAll("li")).map((li) =>
      li.textContent!.replace(/\s+/g, " ").trim(),
    );
    expect(runTexts[0]).toContain("Ejecución #2");
    expect(runTexts[1]).toContain("Ejecución #1");
    expect(details.textContent).not.toContain("Ejecución #3");
  });

  it("toggles inline tool details on click", async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url === activityUrl(9)) {
        return Promise.resolve(
          activityResponse({
            busy: true,
            run: {
              id: 3,
              started_at: ts,
              finished_at: null,
              status: "running",
              round: 1,
              tokens: 10,
              tools: 1,
              current: null,
            },
            rounds: [
              {
                n: 1,
                tools: [{ name: "a", label: "Lista", status: "ok", started_at: ts, ms: 1500 }],
              },
            ],
          }),
        );
      }
      return Promise.resolve(activityResponse());
    });

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" onClose={() => {}} />);
    });
    await flush();

    const map = container.querySelector("[data-agent-map]")!;
    const node = map.querySelector("[data-tool-node]")!;
    expect(node.getAttribute("aria-expanded")).toBe("false");
    expect(map.querySelector("[data-tool-details]")).toBeNull();

    await click(node);
    expect(node.getAttribute("aria-expanded")).toBe("true");
    const details = map.querySelector("[data-tool-details]")!;
    expect(details.querySelector("code")!.textContent).toBe("a");
    expect(details.textContent).toContain("Correcta");
    expect(details.textContent).toContain("1,5 s");
    expect(details.textContent).toContain("Herramienta");
    expect(details.textContent).toContain("Inicio");
    expect(details.textContent).toContain("Duración");

    await click(node);
    expect(node.getAttribute("aria-expanded")).toBe("false");
    expect(map.querySelector("[data-tool-details]")).toBeNull();
  });

  it("renders the idle state", async () => {
    (api.get as any).mockResolvedValue(activityResponse());

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" onClose={() => {}} />);
    });
    await flush();

    const map = container.querySelector("[data-agent-map]")!;
    expect(map.querySelector("[data-agent-node]")!.textContent).toContain(
      "El agente no ha trabajado todavía en esta conversación.",
    );
    expect(
      map.querySelector("[data-agent-map-subtitle]")!.textContent,
    ).toContain("0 herramientas");
    expect(map.textContent).toContain("Sin tareas en segundo plano.");
    expect(map.textContent).toContain("0 tareas en segundo plano");
    expect(map.textContent).toContain("Ejecuciones anteriores (0)");
    expect(map.querySelector('[class*="motion-safe:animate-ping"]')).toBeNull();
  });

  it("close button and Escape call onClose", async () => {
    const onClose = vi.fn();
    (api.get as any).mockResolvedValue(activityResponse());

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" onClose={onClose} />);
    });
    await flush();

    const closeBtn = container.querySelector("[data-agent-map-close]")!;
    expect(closeBtn.getAttribute("aria-label")).toBe(
      "Cerrar el mapa del agente",
    );
    await click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);

    await esc(document.body);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("polls every ACTIVITY_POLL_MS while busy and stops when idle", async () => {
    vi.useFakeTimers();
    (api.get as any)
      .mockResolvedValueOnce(
        activityResponse({
          busy: true,
          run: { id: 9, started_at: ts, finished_at: null, status: "running", round: 1, tokens: 1, tools: 1, current: null },
        }),
      )
      .mockResolvedValueOnce(
        activityResponse({
          busy: true,
          run: { id: 9, started_at: ts, finished_at: null, status: "running", round: 2, tokens: 2, tools: 2, current: null },
        }),
      )
      .mockResolvedValue(activityResponse());

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" onClose={() => {}} />);
    });
    await flush();

    expect(activityCalls(9)).toBe(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_MS);
    });
    expect(activityCalls(9)).toBe(2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ACTIVITY_POLL_MS);
    });
    expect(activityCalls(9)).toBe(3);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(activityCalls(9)).toBe(3);
  });

  it("does not poll when the first response is idle", async () => {
    vi.useFakeTimers();
    (api.get as any).mockResolvedValue(activityResponse());

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" onClose={() => {}} />);
    });
    await flush();
    expect(activityCalls(9)).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(activityCalls(9)).toBe(1);
  });

  it("stops polling when closed", async () => {
    vi.useFakeTimers();
    (api.get as any).mockResolvedValue(
      activityResponse({
        busy: true,
        run: { id: 9, started_at: ts, finished_at: null, status: "running", round: 1, tokens: 1, tools: 1, current: null },
      }),
    );

    function Harness() {
      const [open, setOpen] = useState(true);
      return open ? (
        <AgentMapOverlay sessionId={9} title="T" busy onClose={() => setOpen(false)} />
      ) : null;
    }

    act(() => {
      root.render(<Harness />);
    });
    await flush();
    expect(activityCalls(9)).toBe(1);

    await click(container.querySelector("[data-agent-map-close]")!);
    expect(container.querySelector("[data-agent-map]")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(activityCalls(9)).toBe(1);
  });

  it("stops polling on unmount while busy", async () => {
    vi.useFakeTimers();
    (api.get as any).mockResolvedValue(
      activityResponse({
        busy: true,
        run: { id: 9, started_at: ts, finished_at: null, status: "running", round: 1, tokens: 1, tools: 1, current: null },
      }),
    );

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" busy onClose={() => {}} />);
    });
    await flush();
    expect(activityCalls(9)).toBe(1);

    act(() => root.unmount());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(activityCalls(9)).toBe(1);
  });

  it("restarts polling when externalBusy goes true and does a final fetch when it stops", async () => {
    vi.useFakeTimers();
    (api.get as any).mockResolvedValue(activityResponse());

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" busy={false} onClose={() => {}} />);
    });
    await flush();
    expect(activityCalls(9)).toBe(1);

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" busy={true} onClose={() => {}} />);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(activityCalls(9)).toBe(2);

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" busy={false} onClose={() => {}} />);
    });
    await flush();
    expect(activityCalls(9)).toBe(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(activityCalls(9)).toBe(3);
  });

  it("shows the error state", async () => {
    (api.get as any).mockRejectedValue(new Error("network"));

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" busy onClose={() => {}} />);
    });
    await flush();

    expect(container.textContent).toContain(
      "No se pudo cargar la actividad del agente.",
    );
  });

  it("stops polling after a 404", async () => {
    vi.useFakeTimers();
    (api.get as any).mockRejectedValue(
      new ApiError(404, "not_found", "gone"),
    );

    act(() => {
      root.render(<AgentMapOverlay sessionId={9} title="T" busy onClose={() => {}} />);
    });
    await flush();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(activityCalls(9)).toBe(1);
    expect(container.textContent).toContain(
      "No se pudo cargar la actividad del agente.",
    );
  });
});

describe("AssistantPanel integration", () => {
  function mockRoutes(overrides: Record<string, any> = {}) {
    (api.get as any).mockImplementation((url: string) => {
      if (url === sessionUrl(5))
        return Promise.resolve(
          sessionResponse({ busy: false, ...overrides.session }),
        );
      if (url === activityUrl(5))
        return Promise.resolve(
          activityResponse({ busy: false, ...overrides.activity }),
        );
      return Promise.resolve([]);
    });
  }
  async function renderPanel() {
    localStorage.setItem("bizview.assistantPanel.mode", "docked");
    localStorage.setItem("bizview.assistantPanel.session", "5");
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
    await flush();
    await flush();
  }
  const map = () => container.querySelector("[data-agent-map]");

  it("opens as a floating overlay over the transcript from the header toggle", async () => {
    mockRoutes();
    await renderPanel();

    const toggle = container.querySelector("[data-agent-map-toggle]")!;
    expect(toggle.getAttribute("aria-pressed")).toBe("false");

    await click(toggle);
    expect(map()).not.toBeNull();
    expect(toggle.getAttribute("aria-pressed")).toBe("true");
    expect(
      container
        .querySelector('[role="log"]')!
        .parentElement!.contains(map()),
    ).toBe(true);
    expect(container.querySelector("[data-chat-area]")!.className).not.toContain(
      "hidden",
    );
    expect(container.querySelector("textarea")!.hasAttribute("disabled")).toBe(
      false,
    );
    expect(map()!.getAttribute("role")).toBe("region");
    expect(container.querySelector("[aria-modal]")).toBeNull();
    expect(container.querySelector('[role="dialog"]')).toBeNull();

    await click(toggle);
    expect(map()).toBeNull();
  });

  it("Esc closes the map first (restoring focus), then closes the panel", async () => {
    mockRoutes();
    await renderPanel();

    await click(
      container.querySelector("[data-agent-map-open]")! as HTMLElement,
    );
    expect(map()).not.toBeNull();

    await esc(container.querySelector("textarea")!);
    expect(map()).toBeNull();
    expect(document.activeElement).toBe(
      container.querySelector("[data-agent-map-open]"),
    );
    expect(document.getElementById("assistant-panel")).not.toBeNull();

    await esc(container.querySelector("textarea")!);
    expect(document.getElementById("assistant-panel")).toBeNull();
  });

  it("composer pill opens/closes the map and restores focus", async () => {
    mockRoutes({
      session: {
        messages: [
          { id: 1, role: "user", content: "hola", created_at: ts },
          { id: 2, role: "tool", content: "x", tool_name: "list_sources", created_at: ts },
          { id: 3, role: "tool", content: "y", tool_name: "describe_source", created_at: ts },
          { id: 4, role: "assistant", content: "ok", created_at: ts },
          { id: 5, role: "user", content: "más", created_at: ts },
          { id: 6, role: "tool", content: "z", tool_name: "run_preview", created_at: ts },
          { id: 7, role: "tool", content: "La vista previa terminó.", tool_name: "preview", created_at: ts },
        ],
      },
    });
    await renderPanel();

    const pill = container.querySelector("[data-agent-map-pill]")!;
    expect(pill.textContent).toContain("1 herramienta");
    expect(pill.getAttribute("aria-label")).toBe(
      "Mapa del agente: 1 herramienta",
    );
    expect(pill.getAttribute("aria-pressed")).toBe("false");

    await click(pill);
    expect(map()).not.toBeNull();
    expect(pill.getAttribute("aria-pressed")).toBe("true");

    await click(container.querySelector("[data-agent-map-close]")!);
    expect(map()).toBeNull();
    expect(document.activeElement).toBe(pill);
  });

  it("composer pill dot pulses while busy", async () => {
    mockRoutes({ session: { busy: true } });
    await renderPanel();

    const pill = container.querySelector("[data-agent-map-pill]")!;
    expect(pill.querySelector('[class*="motion-safe:animate-ping"]')).not.toBeNull();
  });

  it("composer pill dot does not pulse while idle", async () => {
    mockRoutes();
    await renderPanel();

    const pill = container.querySelector("[data-agent-map-pill]")!;
    expect(pill.querySelector('[class*="motion-safe:animate-ping"]')).toBeNull();
  });
});

describe("Draft review page (T058)", () => {
  function mockRoutes() {
    (api.get as any).mockImplementation((url: string) => {
      if (url === sessionUrl(7)) {
        return Promise.resolve(
          sessionResponse({
            id: 7,
            title: "Facturas",
            busy: false,
            model: "gpt-test",
            tokens_used: 1200,
            token_budget: 10000,
          }),
        );
      }
      if (url === activityUrl(7)) {
        return Promise.resolve(
          activityResponse({
            run: {
              id: 1,
              started_at: ts,
              finished_at: "2026-10-03T12:00:09Z",
              status: "done",
              round: 2,
              tokens: 1200,
              tools: 2,
              current: null,
            },
            rounds: [
              {
                n: 1,
                tools: [
                  {
                    name: "list_sources",
                    label: "Lista de fuentes",
                    status: "ok",
                    started_at: ts,
                    ms: 1500,
                  },
                ],
              },
              {
                n: 2,
                tools: [
                  {
                    name: "run_preview",
                    label: "Vista previa",
                    status: "error",
                    started_at: ts,
                    ms: 900,
                  },
                ],
              },
            ],
            runs: [
              {
                id: 1,
                started_at: ts,
                finished_at: "2026-10-03T12:00:09Z",
                status: "done",
                rounds: 2,
                tokens: 1200,
                tools: 2,
              },
            ],
          }),
        );
      }
      return Promise.resolve([]);
    });
  }

  async function renderPage() {
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
    await flush();
    await flush();
  }

  function headerButton(): HTMLButtonElement | null {
    const buttons = Array.from(container.querySelectorAll("button"));
    return (
      buttons.find(
        (btn) =>
          btn.textContent?.trim() === "Mapa del agente" &&
          btn.hasAttribute("aria-pressed"),
      ) ?? null
    );
  }

  function indicatorButton(): HTMLButtonElement | null {
    return container.querySelector("[data-agent-map-open]");
  }

  function map(): HTMLElement | null {
    return container.querySelector("[data-agent-map]");
  }

  it("opens from the header button as a non-modal region with nodes; Esc closes and returns focus", async () => {
    mockRoutes();
    await renderPage();

    expect(map()).toBeNull();
    expect(headerButton()?.getAttribute("aria-pressed")).toBe("false");

    const btn = headerButton()!;
    act(() => btn.focus());
    await click(btn);

    expect(map()).not.toBeNull();
    expect(headerButton()?.getAttribute("aria-pressed")).toBe("true");
    expect(map()?.getAttribute("role")).toBe("region");
    expect(map()?.getAttribute("aria-label")).toBe("Mapa del agente");
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector("[aria-modal]")).toBeNull();

    await flush();

    expect(container.querySelector("[data-agent-map-subtitle]")?.textContent).toContain(
      "2 herramientas",
    );
    expect(container.querySelector("[data-agent-node]")?.textContent).toContain("Facturas");
    expect(container.querySelector("[data-agent-node]")?.textContent).toContain("gpt-test");

    const tools = Array.from(container.querySelectorAll("[data-tool-node]"));
    expect(tools).toHaveLength(2);
    expect(tools.map((n) => n.getAttribute("data-tool-status"))).toEqual(["ok", "error"]);
    expect(container.textContent).toContain("Lista de fuentes");
    expect(container.textContent).toContain("Vista previa");

    expect(headerButton()?.disabled).toBe(false);
    expect(document.querySelector("[inert]")).toBeNull();

    act(() => {
      document.body.focus();
    });
    await esc(document.body);

    expect(map()).toBeNull();
    expect(document.activeElement).toBe(headerButton());
    expect(headerButton()?.getAttribute("aria-pressed")).toBe("false");
  });

  it("opens from the session indicator; × closes and returns focus", async () => {
    mockRoutes();
    await renderPage();

    expect(indicatorButton()).not.toBeNull();
    expect(indicatorButton()?.querySelector("[data-session-indicator]")).not.toBeNull();

    const btn = indicatorButton()!;
    act(() => btn.focus());
    await click(btn);

    expect(map()).not.toBeNull();

    await click(container.querySelector("[data-agent-map-close]")!);

    expect(map()).toBeNull();
    expect(document.activeElement).toBe(indicatorButton());
  });

  it("header button toggles the map closed", async () => {
    mockRoutes();
    await renderPage();

    expect(map()).toBeNull();

    const btn = headerButton()!;
    await click(btn);
    expect(map()).not.toBeNull();

    await click(btn);
    expect(map()).toBeNull();
  });

  it("fetches the session's activity", async () => {
    mockRoutes();
    await renderPage();

    await click(headerButton()!);
    await flush();

    expect(api.get).toHaveBeenCalledWith(activityUrl(7));
  });
});
