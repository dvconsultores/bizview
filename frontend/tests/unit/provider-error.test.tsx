/** Feature 035 (US1, FR-005/FR-016): a failing provider says the code, its own words, the model
 * and one action; the technical details — timestamp, reference, log command — stay collapsed. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProviderError } from "../../src/components/assistant/ProviderError";
import type { ProviderErrorPayload } from "../../src/api/types";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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
});

const credit: ProviderErrorPayload = {
  code: "no_credit",
  detail: "Insufficient Balance",
  provider: "anthropic",
  model: "deepseek-flash",
  at: "2026-10-25T21:12:00Z",
  request_id: "a1b2c3d4",
  action: "admin_ai",
  blocked: true,
};

async function render(error: ProviderErrorPayload, onRetry?: () => void) {
  await act(async () => {
    root?.render(
      <MemoryRouter>
        <ProviderError error={error} onRetry={onRetry} />
      </MemoryRouter>,
    );
  });
}

describe("provider error bubble (feature 035)", () => {
  it("shows the translated reason, the code and the provider's own words", async () => {
    await render(credit);
    const alert = container.querySelector('[role="alert"]');
    expect(alert).toBeTruthy();
    expect(alert!.textContent).toContain(t.ai.errorCodes.no_credit);
    expect(alert!.textContent).toContain("no_credit");
    expect(alert!.textContent).toContain("Insufficient Balance");
    expect(alert!.textContent).toContain("deepseek-flash");
    expect(alert!.textContent).toContain("anthropic");
  });

  it("sends a credit problem to Administración → IA", async () => {
    await render(credit);
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("/admin/ia");
    expect(link?.textContent).toContain(t.ai.action.admin_ai);
    expect(container.textContent).toContain(t.ai.blockedTag);
  });

  it("offers Reintentar for a transient code and says how long to wait", async () => {
    const onRetry = vi.fn();
    await render(
      { ...credit, code: "rate_limited", action: "retry", retry_after: 12, blocked: false },
      onRetry,
    );
    expect(container.textContent).toContain(t.ai.retryAfter(12));
    const button = [...container.querySelectorAll("button")].find((b) =>
      b.textContent?.includes(t.ai.action.retry),
    );
    expect(button).toBeTruthy();
    await act(async () => button!.click());
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("keeps the log command and the reference behind Detalles técnicos", async () => {
    await render(credit);
    const details = container.querySelector("details");
    expect(details).toBeTruthy();
    expect(details!.open).toBe(false);
    expect(details!.textContent).toContain(t.ai.details.title);
    expect(details!.textContent).toContain(t.ai.details.cmd);
    expect(details!.textContent).toContain("a1b2c3d4");
  });
});
