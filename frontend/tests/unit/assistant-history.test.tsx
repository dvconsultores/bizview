import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), del: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  },
}));

import { api } from "../../src/api/client";
import { AssistantHistory, relativeTime } from "../../src/components/assistant/AssistantHistory";
import { activate } from "../../src/i18n/live";
import { t } from "../../src/i18n/es";

describe("relativeTime", () => {
  const now = new Date("2026-10-03T12:00:00Z").getTime();
  it("returns short Spanish relative times", () => {
    expect(relativeTime(new Date(now - 30_000).toISOString(), now)).toBe("ahora");
    expect(relativeTime(new Date(now - 5 * 60_000).toISOString(), now)).toBe("5 min");
    expect(relativeTime(new Date(now - 3 * 3_600_000).toISOString(), now)).toBe("3 h");
    expect(relativeTime(new Date(now - 2 * 86_400_000).toISOString(), now)).toBe("2 d");
  });
  it("says now in English (022 T051)", () => {
    activate("en");
    try {
      expect(relativeTime(new Date(now - 30_000).toISOString(), now)).toBe("now");
    } finally {
      activate("es");
    }
  });
});

describe("AssistantHistory", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
    vi.mocked(api.del).mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("lists conversations, hides archived ones in a group, filters and selects", async () => {
    const now = Date.now();
    const iso = (ms: number) => new Date(now - ms).toISOString();
    vi.mocked(api.get).mockResolvedValue({ sessions: [
      { id: 2, title: "Ventas", status: "open", updated_at: iso(3_600_000), tokens_used: 1, token_budget: 9 },
      { id: 3, title: "Inventario", status: "applied", updated_at: iso(86_400_000), tokens_used: 1, token_budget: 9 },
      { id: 4, title: "Viejo", status: "archived", updated_at: iso(86_400_000), tokens_used: 1, token_budget: 9 },
    ] } as any);
    const onSelect = vi.fn();
    await act(async () => {
      root.render(<AssistantHistory currentId={2} onSelect={onSelect} onNew={vi.fn()} />);
    });
    const button = container.querySelector<HTMLButtonElement>('button[aria-label="Conversaciones"]')!;
    await act(async () => button.click());

    expect(api.get).toHaveBeenCalledWith("/api/assistant/sessions");
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(container.textContent).toContain("Ventas");
    expect(container.textContent).toContain("Inventario");
    expect(container.textContent).not.toContain("Viejo");
    const group = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent?.includes("Conversaciones archivadas"))!;
    expect(group.textContent).toContain("1");

    const search = container.querySelector<HTMLInputElement>('input[type="search"]')!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(search, "inv");
      search.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(container.textContent).toContain("Inventario");
    expect(container.textContent).not.toContain("Ventas");

    const row = Array.from(container.querySelectorAll<HTMLButtonElement>("li button"))
      .find((b) => b.textContent?.includes("Inventario"))!;
    await act(async () => row.click());
    expect(onSelect).toHaveBeenCalledWith(3);
    expect(container.querySelector("#assistant-history-popover")).toBeNull();
  });

  it("deletes a conversation, active or archived, after confirming", async () => {
    const iso = new Date().toISOString();
    vi.mocked(api.get).mockResolvedValue({ sessions: [
      { id: 2, title: "Ventas", status: "open", updated_at: iso, tokens_used: 1, token_budget: 9 },
      { id: 4, title: "Viejo", status: "archived", updated_at: iso, tokens_used: 1, token_budget: 9 },
    ] } as any);
    vi.mocked(api.del).mockResolvedValue(undefined as never);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    await act(async () => {
      root.render(<AssistantHistory currentId={2} onSelect={vi.fn()} onNew={vi.fn()} />);
    });
    await act(async () => {
      container.querySelector<HTMLButtonElement>('button[aria-label="Conversaciones"]')!.click();
    });
    const trash = (title: string) =>
      container.querySelector<HTMLButtonElement>(`li button[aria-label="${t.assistant.deleteSession} ${title}"]`);
    expect(trash("Ventas")).not.toBeNull();                 // active row
    await act(async () => {
      Array.from(container.querySelectorAll("button"))
        .find((b) => b.textContent?.includes("Conversaciones archivadas"))!.click();
    });
    expect(trash("Viejo")).not.toBeNull();                  // archived row, the ones that pile up
    await act(async () => trash("Viejo")!.click());
    expect(api.del).toHaveBeenCalledWith("/api/assistant/sessions/4");
    confirm.mockRestore();
  });
});
