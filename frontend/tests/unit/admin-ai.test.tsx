/** Feature 035 (US1, FR-008): Probar says which half failed — the answer or the tool call — names
 * the code with its action, and lists the models the endpoint reports so a wrong AI_MODEL shows. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AIStatus, AITestResult } from "../../src/api/types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const status: AIStatus = {
  enabled: true,
  provider: "anthropic",
  model: "deepseek-flash",
  base_url: "https://api.deepseek.com/anthropic",
  key_configured: true,
  timeout_seconds: 30,
  missing: [],
  last_ok_at: "2026-10-25T17:35:00Z",
  last_error_code: "no_credit",
  last_error_at: "2026-10-25T21:12:00Z",
  last_error_detail: "Insufficient Balance",
  last_model: "deepseek-flash",
  healthy: false,
  blocking_code: "no_credit",
};
const failing: AITestResult = {
  ok: false,
  provider: "anthropic",
  model: "deepseek-flash",
  latency_ms: 420,
  reply: null,
  error: { code: "no_credit", message: "no_credit", detail: "Insufficient Balance", action: "admin_ai" },
  tool_call: { ok: false, name: null, latency_ms: null, error: { code: "no_credit", message: "no_credit" } },
  models: ["deepseek-chat", "deepseek-reasoner"],
};
const healthyResult: AITestResult = {
  ok: true,
  provider: "anthropic",
  model: "deepseek-flash",
  latency_ms: 210,
  reply: "ok",
  error: null,
  tool_call: { ok: true, name: "list_projects", latency_ms: 190, error: null },
  models: ["deepseek-chat", "deepseek-flash"],
};

let next: AITestResult = failing;
vi.mock("../../src/api/client", () => ({
  api: {
    get: vi.fn(async () => status),
    post: vi.fn(async () => next),
    patch: vi.fn(),
    del: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
  askReauth: vi.fn(async () => true),
  qs: () => "",
}));

import { AI } from "../../src/pages/admin/AI";
import { t } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  next = failing;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

async function open() {
  await act(async () => root?.render(<MemoryRouter><AI /></MemoryRouter>));
  await act(async () => {});
}

async function test() {
  const button = [...container.querySelectorAll("button")].find((b) =>
    b.textContent?.includes(t.ai.test),
  );
  expect(button, "the Probar button").toBeTruthy();
  await act(async () => button!.click());
  await act(async () => {});
}

describe("Administración → IA (feature 035)", () => {
  it("shows how the last real call went, without the key", async () => {
    await open();
    expect(container.textContent).toContain(t.ai.lastError);
    expect(container.textContent).toContain("no_credit");
    expect(container.textContent).toContain("Insufficient Balance");
  });

  it("names the failing code, its action and the provider's words", async () => {
    await open();
    await test();
    expect(container.textContent).toContain(t.ai.testFail);
    expect(container.textContent).toContain(t.ai.errorCodes.no_credit);
    expect(container.textContent).toContain(t.ai.action.admin_ai);
    expect(container.textContent).toContain("Insufficient Balance");
  });

  it("lists the models the endpoint reports and flags a wrong AI_MODEL", async () => {
    await open();
    await test();
    expect(container.textContent).toContain(t.ai.models);
    expect(container.textContent).toContain("deepseek-reasoner");
    expect(container.textContent).toContain(t.ai.modelsMissing);
  });

  it("reports both halves when the model answers and calls no tool", async () => {
    next = { ...healthyResult, tool_call: { ok: false, name: null, latency_ms: null, error: null } };
    await open();
    await test();
    expect(container.textContent).toContain(t.ai.testOk);
    expect(container.textContent).toContain(t.ai.toolCall);
    expect(container.textContent).toContain(t.ai.toolCallFail);
    expect(container.textContent).not.toContain(t.ai.modelsMissing);
  });

  it("keeps the log command collapsed behind Detalles técnicos", async () => {
    await open();
    await test();
    const details = container.querySelector("details");
    expect(details?.open).toBe(false);
    expect(details?.textContent).toContain(t.ai.details.cmd);
  });
});
