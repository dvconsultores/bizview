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
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  messages: [],
  busy: false,
  model: "deepseek-v4-pro",
} as unknown as AssistantSession;

describe("sessionIndicator", () => {
  it("working beats ready", () => {
    const r = sessionIndicator({ ...base, busy: true, tokens_used: 900_000 }, false);
    expect(r.state).toBe("working");
    expect(r.label).toBe("Trabajando");
  });

  it("working override", () => {
    const r = sessionIndicator({ ...base, busy: false }, true);
    expect(r.state).toBe("working");
  });

  it("ready when idle", () => {
    const r = sessionIndicator({ ...base, busy: false, tokens_used: 1 });
    expect(r.state).toBe("ready");
    expect(r.label).toBe("Lista");
  });

  it("reports the tokens spent, never a percentage of a cap", () => {
    // Owner, 2026-10-21 ("make the ai unlimited"): there is no budget to be a percentage of.
    expect(sessionIndicator(base).tokensText).toBe("42.000");
    expect(sessionIndicator({ ...base, tokens_used: 9_000_000 }).tokensText).toBe("9.000.000");
    expect(sessionIndicator({ ...base, tokens_used: 9_000_000 }).state).toBe("ready");
  });

  it("aria label with model", () => {
    const r = sessionIndicator(base);
    expect(r.ariaLabel).toBe(
      "Estado de la sesión: Lista, modelo deepseek-v4-pro, 42.000 tokens usados",
    );
  });

  it("aria label without model", () => {
    const r = sessionIndicator({ ...base, model: null });
    expect(r.ariaLabel).toBe("Estado de la sesión: Lista, 42.000 tokens usados");
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
    expect(el.getAttribute("aria-label")).toContain("42.000 tokens usados");
    expect(el.textContent).toContain("Trabajando");
    expect(el.textContent).toContain("deepseek-v4-pro");
    expect(el.textContent).toContain("42.000");
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
    expect(container.textContent).toContain("42.000");
    unmount();
    container.remove();
  });
});
