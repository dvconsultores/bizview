import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { SessionIndicator, sessionIndicator } from "../../src/components/assistant/SessionIndicator";
import type { AssistantSession } from "../../src/api/types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const base: AssistantSession = {
  id: 7,
  title: "Prueba",
  status: "open",
  draft: null,
  validation: null,
  preview: null,
  applied_version_id: null,
  tokens_used: 42_000,
  token_budget: 100_000,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  messages: [],
  busy: false,
  model: "deepseek-v4-pro",
} as unknown as AssistantSession;

describe("sessionIndicator", () => {
  it("working beats no-budget", () => {
    const r = sessionIndicator({ ...base, busy: true, tokens_used: 200_000 }, false);
    expect(r.state).toBe("working");
    expect(r.label).toBe("Trabajando");
  });

  it("working override", () => {
    const r = sessionIndicator({ ...base, busy: false }, true);
    expect(r.state).toBe("working");
  });

  it("no budget", () => {
    const r = sessionIndicator({ ...base, busy: false, tokens_used: 100_000 });
    expect(r.state).toBe("no_budget");
    expect(r.label).toBe("Sin presupuesto");
  });

  it("token budget zero means no budget", () => {
    const r = sessionIndicator({ ...base, busy: false, token_budget: 0, tokens_used: 0 });
    expect(r.state).toBe("no_budget");
    expect(r.budgetText).toBe("100 %+");
  });

  it("ready", () => {
    const r = sessionIndicator({ ...base, busy: false, tokens_used: 1 });
    expect(r.state).toBe("ready");
    expect(r.label).toBe("Lista");
  });

  it("budget text", () => {
    expect(sessionIndicator(base).budgetText).toBe("42 %");
    expect(sessionIndicator({ ...base, tokens_used: 100_000 }).budgetText).toBe("100 %");
    expect(sessionIndicator({ ...base, tokens_used: 100_001 }).budgetText).toBe("100 %+");
  });

  it("aria label with model", () => {
    const r = sessionIndicator(base);
    expect(r.ariaLabel).toBe(
      "Estado de la sesión: Lista, modelo deepseek-v4-pro, presupuesto usado 42 %",
    );
  });

  it("aria label without model", () => {
    const r = sessionIndicator({ ...base, model: null });
    expect(r.ariaLabel).toBe("Estado de la sesión: Lista, presupuesto usado 42 %");
  });

  it("uses budget_max when the original budget is spent", () => {
    const result = sessionIndicator({
      ...base,
      tokens_used: 100_000,
      token_budget: 100_000,
      budget_max: 400_000,
    });

    expect(result.state).toBe("ready");
    expect(result.label).toBe("Lista");
    expect(result.budgetText).toBe("25 %");
  });

  it("hits no_budget only at the max", () => {
    const result = sessionIndicator({
      ...base,
      tokens_used: 400_000,
      token_budget: 400_000,
      budget_max: 400_000,
    });

    expect(result.state).toBe("no_budget");
    expect(result.label).toBe("Sin presupuesto");
    expect(result.budgetText).toBe("100 %");
  });

  it("shows over-budget only past the max", () => {
    const result = sessionIndicator({
      ...base,
      tokens_used: 400_001,
      token_budget: 400_000,
      budget_max: 400_000,
    });

    expect(result.state).toBe("no_budget");
    expect(result.budgetText).toBe("100 %+");
  });

  it("ignores a smaller budget_max", () => {
    const result = sessionIndicator({
      ...base,
      tokens_used: 42_000,
      token_budget: 100_000,
      budget_max: 50_000,
    });

    expect(result.state).toBe("ready");
    expect(result.budgetText).toBe("42 %");
  });

  it("supports token_budget 0 with budget_max", () => {
    const result = sessionIndicator({
      ...base,
      tokens_used: 50_000,
      token_budget: 0,
      budget_max: 200_000,
    });

    expect(result.state).toBe("ready");
    expect(result.budgetText).toBe("25 %");
  });

  it("uses max-based percentage in the aria label", () => {
    const result = sessionIndicator({
      ...base,
      tokens_used: 100_000,
      token_budget: 100_000,
      budget_max: 400_000,
    });

    expect(result.ariaLabel).toContain(
      "Estado de la sesión: Lista, modelo deepseek-v4-pro, presupuesto usado 25 %",
    );
  });
});

describe("SessionIndicator", () => {
  function renderIndicator(session: AssistantSession) {
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: Root | undefined;
    act(() => {
      root = createRoot(container);
      root.render(<SessionIndicator session={session} working={false} />);
    });
    return { container, unmount: () => act(() => root!.unmount()) };
  }

  it("renders working indicator", () => {
    const { container, unmount } = renderIndicator({ ...base, busy: true });
    const el = container.querySelector("[data-session-indicator]")!;
    expect(el).not.toBeNull();
    expect(el.getAttribute("role")).toBe("status");
    expect(el.getAttribute("aria-label")).toContain("Trabajando");
    expect(el.getAttribute("aria-label")).toContain("deepseek-v4-pro");
    expect(el.getAttribute("aria-label")).toContain("42 %");
    expect(el.textContent).toContain("Trabajando");
    expect(el.textContent).toContain("deepseek-v4-pro");
    expect(el.textContent).toContain("42 %");
    expect(container.querySelector('[class*="animate-ping"]')).not.toBeNull();
    unmount();
    container.remove();
  });

  it("renders ready indicator without ping", () => {
    const { container, unmount } = renderIndicator(base);
    const el = container.querySelector("[data-session-indicator]")!;
    expect(el).not.toBeNull();
    expect(el.textContent).toContain("Lista");
    expect(container.querySelector('[class*="animate-ping"]')).toBeNull();
    unmount();
    container.remove();
  });

  it("stays inside its box and hides the model below sm", () => {
    const { container, unmount } = renderIndicator({ ...base, busy: true });
    const indicator = container.querySelector("[data-session-indicator]");
    expect(indicator).not.toBeNull();
    expect(indicator!.className).toContain("overflow-hidden");
    const modelSpan = Array.from(container.querySelectorAll("span")).find(
      (span) => span.getAttribute("title") === "deepseek-v4-pro",
    );
    expect(modelSpan).toBeDefined();
    expect(modelSpan!.classList.contains("hidden")).toBe(true);
    expect(modelSpan!.classList.contains("sm:inline")).toBe(true);
    expect(container.textContent).toContain("Trabajando");
    expect(container.textContent).toContain("42 %");
    unmount();
    container.remove();
  });
});
