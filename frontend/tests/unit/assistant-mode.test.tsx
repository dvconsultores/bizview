import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModePill, ModeSelector } from "../../src/components/assistant/ModeSelector";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() },
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
  askReauth: vi.fn(),
  qs: () => "",
}));

const ts = "2026-10-20T12:00:00Z";
const base = {
  id: 7,
  title: "Prueba",
  status: "open",
  mode: "auto",
  contract_status: "none",
  busy: false,
  tokens_used: 10,
  created_at: ts,
  updated_at: ts,
  draft: null,
  validation: null,
  preview: null,
  applied_version_id: null,
  messages: [],
} as any;

let container: HTMLDivElement;
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

function options() {
  return Array.from(container.querySelectorAll("[data-mode-option]")) as HTMLButtonElement[];
}

function trigger() {
  return container.querySelector("[data-mode-selector] button") as HTMLButtonElement;
}

describe("ModeSelector (feature 028, two modes)", () => {
  it("shows the current mode and opens a two-entry menu", async () => {
    await act(async () => {
      root.render(<ModeSelector session={base} onSelect={() => {}} onRequestAuto={() => {}} />);
    });
    expect(trigger().textContent).toContain("Auto");
    expect(container.querySelector('[role="menu"]')).toBeNull();

    await act(async () => {
      trigger().click();
    });
    const menu = container.querySelector('[role="menu"]')!;
    expect(menu.getAttribute("aria-label")).toBe("Modo del asistente");
    expect(options().map((b) => b.textContent)).toEqual([
      "PreguntarSolo lee y explica; no escribe ni aplica nada.",
      "AutoHace todo el run sin preguntar: escribe, previsualiza y aplica.",
    ]);
    expect(options().map((b) => b.getAttribute("aria-checked"))).toEqual(["false", "true"]);
  });

  it("switches down at once and asks for the run authorisation for Auto", async () => {
    const selected: string[] = [];
    let asked = 0;
    await act(async () => {
      root.render(
        <ModeSelector
          session={base}
          onSelect={(mode) => selected.push(mode)}
          onRequestAuto={() => {
            asked += 1;
          }}
        />,
      );
    });
    await act(async () => {
      trigger().click();
    });
    await act(async () => {
      options()[0].click();
    });
    expect(selected).toEqual(["ask"]);

    await act(async () => {
      trigger().click();
    });
    await act(async () => {
      trigger().click();          // Auto is already the mode: nothing happens
    });
    expect(asked).toBe(0);

    await act(async () => {
      root.render(
        <ModeSelector
          session={{ ...base, mode: "ask" }}
          onSelect={(mode) => selected.push(mode)}
          onRequestAuto={() => {
            asked += 1;
          }}
        />,
      );
    });
    await act(async () => {
      trigger().click();
    });
    await act(async () => {
      options()[1].click();
    });
    expect(asked).toBe(1);
    expect(selected).toEqual(["ask"]);
  });

  it("closes with Escape", async () => {
    await act(async () => {
      root.render(<ModeSelector session={base} onSelect={() => {}} onRequestAuto={() => {}} />);
    });
    await act(async () => {
      trigger().click();
    });
    expect(container.querySelector('[role="menu"]')).not.toBeNull();
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(container.querySelector('[role="menu"]')).toBeNull();
  });

  it("shows the pill of each state", async () => {
    await act(async () => {
      root.render(<ModePill session={{ ...base, mode: "ask", contract_status: "none" }} />);
    });
    expect(container.textContent).toBe("Preguntar");

    await act(async () => {
      root.render(<ModePill session={{ ...base, mode: "auto", contract_status: "none" }} />);
    });
    // No contract is the normal state between runs (one opens with the next stage): the pill says
    // just "Auto", never anything that reads like a missing authorisation.
    expect(container.textContent).toBe("Auto");

    await act(async () => {
      root.render(
        <ModePill session={{ ...base, mode: "auto", contract_status: "running", busy: true }} />,
      );
    });
    expect(container.textContent).toBe("Auto · ejecutando");
    expect(container.querySelector("[data-tone]")?.getAttribute("data-tone")).toBe("auto");
  });
});
