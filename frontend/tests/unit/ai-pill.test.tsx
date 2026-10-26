/** Feature 035 (US1/US2, FR-007): the AI state is one pill — off, working, or failing with its
 * code — and the administration home wears it, so an outage is visible before typing. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AIHealth } from "../../src/api/types";
import { AIPill } from "../../src/components/assistant/AIPill";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let health: AIHealth | null = null;
vi.mock("../../src/api/ai", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../src/api/ai")>()),
  useAIHealth: () => health,
}));
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: { role: "admin", is_superuser: true } }),
}));

import { aiHealthState } from "../../src/api/ai";
import { AdminHome } from "../../src/pages/admin/AdminHome";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
  health = null;
});

const ok: AIHealth = {
  configured: true,
  provider: "anthropic",
  model: "deepseek-flash",
  last_ok_at: "2026-10-25T17:35:00Z",
  last_error_code: null,
  last_error_at: null,
};
const failed: AIHealth = {
  ...ok,
  last_error_code: "no_credit",
  last_error_at: "2026-10-25T21:12:00Z",
};

async function render(node: React.ReactNode) {
  await act(async () => root?.render(<MemoryRouter>{node}</MemoryRouter>));
}

describe("AI pill (feature 035)", () => {
  it("says nothing in the composer while the provider is fine", async () => {
    await render(<AIPill health={ok} />);
    expect(container.textContent).toBe("");
  });

  it("names the code and links to Administración → IA while failing", async () => {
    await render(<AIPill health={failed} />);
    expect(container.textContent).toContain("no_credit");
    expect(container.querySelector("a")?.getAttribute("href")).toBe("/admin/ia");
    expect(container.querySelector("a")?.getAttribute("title")).toBe(t.ai.errorCodes.no_credit);
  });

  it("states the healthy case where there is room for it", async () => {
    await render(<AIPill health={ok} compact={false} />);
    expect(container.textContent).toContain(t.ai.pillOk);
  });

  it("goes quiet when the last answer is newer than the last error", () => {
    expect(aiHealthState(ok)).toBe("ok");
    expect(aiHealthState(failed)).toBe("error");
    expect(aiHealthState({ ...failed, configured: false })).toBe("off");
    expect(aiHealthState(null)).toBe("unknown");
  });

  it("shows the pill on the administration home", async () => {
    health = failed;
    await render(<AdminHome />);
    expect(container.textContent).toContain("no_credit");
    expect(container.querySelector('a[href="/admin/ia"]')).toBeTruthy();
  });
});
