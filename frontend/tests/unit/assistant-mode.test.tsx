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
  mode: "edit",
  contract_status: "none",
  busy: false,
  tokens_used: 10,
  token_budget: 100000,
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

function buttons() {
  return Array.from(container.querySelectorAll("[data-mode]")) as HTMLButtonElement[];
}

describe("ModeSelector (feature 028, FR-000)", () => {
  it("renders the three modes as a radiogroup with the current one checked", async () => {
    await act(async () => {
      root.render(
        <ModeSelector session={base} onSelect={() => {}} onRequestAuto={() => {}} />,
      );
    });
    const group = container.querySelector('[role="radiogroup"]')!;
    expect(group.getAttribute("aria-label")).toBe("Modo del asistente");
    const items = buttons();
    expect(items.map((b) => b.textContent)).toEqual(["Preguntar", "Editar", "Auto"]);
    expect(items.map((b) => b.getAttribute("aria-checked"))).toEqual(["false", "true", "false"]);
    // Only the active mode is in the tab order; arrows move between them.
    expect(items.map((b) => b.tabIndex)).toEqual([-1, 0, -1]);
  });

  it("switches down immediately and asks for a contract when choosing Auto", async () => {
    const selected: string[] = [];
    let askedForContract = 0;
    await act(async () => {
      root.render(
        <ModeSelector
          session={base}
          onSelect={(mode) => selected.push(mode)}
          onRequestAuto={() => {
            askedForContract += 1;
          }}
        />,
      );
    });
    await act(async () => {
      buttons()[0].click();
    });
    expect(selected).toEqual(["ask"]);

    await act(async () => {
      buttons()[2].click();
    });
    expect(askedForContract).toBe(1);
    expect(selected).toEqual(["ask"]);          // Auto only activates with a confirmed contract
  });

  it("moves with the arrow keys", async () => {
    const selected: string[] = [];
    await act(async () => {
      root.render(
        <ModeSelector
          session={base}
          onSelect={(mode) => selected.push(mode)}
          onRequestAuto={() => {}}
        />,
      );
    });
    await act(async () => {
      container
        .querySelector('[role="radiogroup"]')!
        .dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    });
    expect(selected).toEqual(["ask"]);
  });

  it("shows the pill of each state", async () => {
    await act(async () => {
      root.render(<ModePill session={{ ...base, mode: "edit", contract_status: "none" }} />);
    });
    expect(container.textContent).toBe("Editar");
    expect(container.querySelector("[data-tone]")?.getAttribute("data-tone")).toBe("muted");

    await act(async () => {
      root.render(
        <ModePill session={{ ...base, mode: "auto", contract_status: "none", busy: false }} />,
      );
    });
    expect(container.textContent).toBe("Auto · sin contrato");

    await act(async () => {
      root.render(
        <ModePill
          session={{ ...base, mode: "auto", contract_status: "running", busy: true }}
        />,
      );
    });
    expect(container.textContent).toBe("Auto · ejecutando");
    expect(container.querySelector("[data-tone]")?.getAttribute("data-tone")).toBe("auto");
  });

  it("keeps the composer's mode in the session state across renders", async () => {
    function Harness() {
      const [session, setSession] = useState(base);
      return (
        <>
          <ModePill session={session} />
          <ModeSelector
            session={session}
            onSelect={(mode) => setSession({ ...session, mode })}
            onRequestAuto={() => {}}
          />
        </>
      );
    }
    await act(async () => {
      root.render(<Harness />);
    });
    await act(async () => {
      buttons()[0].click();
    });
    expect(container.querySelector("[data-mode-pill]")?.textContent).toBe("Preguntar");
    expect(buttons()[0].getAttribute("aria-checked")).toBe("true");
  });
});
