/** Feature 060: a run that ended because the origin was full is amber, explained, and linkable. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
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
vi.mock("../../src/components/Toast", () => ({ useToast: () => vi.fn() }));
// The locale provider reads the account's preference, which this file does not exercise.
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), logout: vi.fn(), refresh: vi.fn() }),
  MFA_SETUP_PATH: "/seguridad/doble-factor",
  safeNext: (next: string | null) => next ?? "/",
}));

import { RunStatus } from "../../src/pages/admin/Integrations";
import type { IntegrationRun } from "../../src/api/types";
import { LocaleProvider } from "../../src/i18n";
import { es } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  localStorage.setItem("bizview.locale", "es");
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  localStorage.clear();
});

function run(over: Partial<IntegrationRun> = {}): IntegrationRun {
  return {
    id: 21,
    kind: "incremental",
    status: "skipped_busy",
    started_at: "2026-11-06T14:00:00Z",
    finished_at: "2026-11-06T14:07:20Z",
    rows: {},
    checks: [],
    message: "La fuente no admite más conexiones ahora (4 intentos, 7 min): FATAL: demasiados",
    busy: { sqlstate: "53300", attempts: 4, waited_s: 420, detail: "FATAL: demasiados clientes" },
    ...over,
  };
}

async function render(node: React.ReactNode) {
  await act(async () => {
    root.render(<LocaleProvider><MemoryRouter>{node}</MemoryRouter></LocaleProvider>);
  });
}

describe("a run the origin could not serve", () => {
  it("is amber and says the source has no free slots — never red", async () => {
    await render(<RunStatus run={run()} />);
    expect(container.textContent).toContain(es.integrations.runBadge.busy);
    // The amber badge of the design system, not the red one a failure wears.
    expect(container.innerHTML).toContain("bg-warning-soft");
    expect(container.textContent).not.toContain(es.integrations.runBadge.failed);
  });

  it("keeps the ordinary statuses as they were", async () => {
    await render(<RunStatus run={run({ status: "failed", busy: {} })} />);
    expect(container.textContent).toContain(es.integrations.runBadge.failed);
    expect(container.innerHTML).toContain("bg-danger-soft");
  });
});
