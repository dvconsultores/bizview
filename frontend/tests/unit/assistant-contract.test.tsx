import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunContractDialog } from "../../src/components/assistant/RunContractDialog";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const confirmContract = vi.fn();
const saveRunProfile = vi.fn();
const confirmNoop = vi.fn();
const runProfiles = vi.fn().mockResolvedValue([]);

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn().mockResolvedValue(undefined), patch: vi.fn(), del: vi.fn() },
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
  askReauth: vi.fn().mockResolvedValue(false),
  qs: () => "",
}));

vi.mock("../../src/api/projects", () => ({
  projectsApi: {
    confirmContract: (...args: unknown[]) => confirmContract(...args),
    saveRunProfile: (...args: unknown[]) => saveRunProfile(...args),
    setMode: () => Promise.resolve(),
    cancelContract: () => Promise.resolve(),
    runProfiles: () => runProfiles(),
  },
}));

const ts = "2026-10-20T12:00:00Z";
const session = {
  id: 7,
  title: "Prueba",
  status: "open",
  mode: "auto",
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
  confirmContract.mockReset();
  saveRunProfile.mockReset();
  onClose.mockReset();
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

/** React reads the native value setter: a plain assignment does not fire its onChange. */
function setValue(element: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
}

const onClose = vi.fn();

async function render() {
  await act(async () => {
    root.render(
      <RunContractDialog
        session={session}
        goal="dashboard de facturas"
        onClose={onClose}
        onConfirmed={() => {}}
      />,
    );
  });
  await act(async () => {});
}

describe("RunContractDialog (one-line authorisation, feature 028)", () => {
  it("explains the defaults instead of showing a form", async () => {
    await render();
    expect(container.textContent).toContain("Contrato del run");
    expect(container.textContent).toContain("Todo el pipeline hasta aplicar");
    // No staging choice, no numeric fields: only the step-up.
    expect(container.querySelectorAll('input[name="stage"]')).toHaveLength(0);
    expect(container.querySelectorAll('input[type="number"]')).toHaveLength(0);
    expect(container.querySelectorAll("select")).toHaveLength(0);
  });

  it("cannot authorise without the password", async () => {
    await render();
    const confirm = container.querySelector("[data-contract-confirm]") as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
  });

  it("authorises with the defaults and the password", async () => {
    confirmContract.mockResolvedValue({ run: {}, session });
    await render();
    const password = container.querySelector('input[type="password"]') as HTMLInputElement;
    await act(async () => {
      setValue(password, "Correct-horse-9");
    });
    const confirm = container.querySelector("[data-contract-confirm]") as HTMLButtonElement;
    expect(confirm.disabled).toBe(false);
    await act(async () => {
      confirm.click();
    });
    expect(confirmContract).toHaveBeenCalledTimes(1);
    const [sessionId, body] = confirmContract.mock.calls[0];
    expect(sessionId).toBe(7);
    expect(body.password).toBe("Correct-horse-9");
    expect(body.code).toBeNull();
    expect(body.contract.stages).toEqual(["draft", "preview", "apply"]);
    expect(body.contract.limits).toBeUndefined();      // the server fills the installation defaults
    expect(body.contract.goal).toBe("dashboard de facturas");
  });

  it("shows the server's step-up error and stays open", async () => {
    const { ApiError } = await import("../../src/api/client");
    confirmContract.mockRejectedValue(new (ApiError as any)(401, "step_up_failed",
      "La contraseña no es correcta.", { password: "invalid" }));
    await render();
    const password = container.querySelector('input[type="password"]') as HTMLInputElement;
    await act(async () => {
      setValue(password, "mala");
    });
    await act(async () => {
      (container.querySelector("[data-contract-confirm]") as HTMLButtonElement).click();
    });
    expect(container.textContent).toContain("La contraseña no es correcta.");
    expect(container.querySelector("[data-run-contract]")).not.toBeNull();
  });

  it("cancels without authorising", async () => {
    await render();
    const cancel = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Cancelar",
    ) as HTMLButtonElement;
    await act(async () => {
      cancel.click();
    });
    expect(onClose).toHaveBeenCalled();
    expect(confirmContract).not.toHaveBeenCalled();
  });
});
