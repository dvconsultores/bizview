import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
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
  qs: (p: Record<string, string | number | undefined | null>) => {
    const parts = Object.entries(p)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
    return parts.length ? `?${parts.join("&")}` : "";
  },
}));

import { api, ApiError } from "../../src/api/client";
import { ShareLinksPanel } from "../../src/components/sharing/ShareLinksPanel";
import { t } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
});

async function flush() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}
function typeInto(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const proto =
    el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
const byText = (text: string) =>
  Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === text,
  ) as HTMLButtonElement | undefined;
const inputByLabel = (label: string) => {
  const l = Array.from(container.querySelectorAll("label")).find(
    (x) => x.textContent?.replace("*", "").trim() === label,
  );
  return l
    ? (document.getElementById(l.htmlFor) as HTMLInputElement)
    : null;
};

const baseState = {
  items: [
    {
      id: 1,
      note: "Para Ana",
      created_by: { id: 2, name: "Luis" },
      created_at: "2026-01-05T08:00:00Z",
      expires_at: "2026-02-05T08:00:00Z",
      revoked_at: null,
      visits: 3,
      last_visit_at: "2026-01-20T18:00:00Z",
      active: true,
    },
    {
      id: 2,
      note: null,
      created_by: { id: 2, name: "Luis" },
      created_at: "2025-11-01T08:00:00Z",
      expires_at: "2025-12-01T08:00:00Z",
      revoked_at: null,
      visits: 1,
      last_visit_at: "2025-11-10T09:00:00Z",
      active: false,
    },
    {
      id: 3,
      note: "Revocado",
      created_by: { id: 2, name: "Luis" },
      created_at: "2025-10-01T08:00:00Z",
      expires_at: "2025-11-01T08:00:00Z",
      revoked_at: "2025-10-15T10:00:00Z",
      visits: 0,
      last_visit_at: null,
      active: false,
    },
  ],
  sharing_enabled: true,
  max_active: 20,
  days: { min: 1, max: 90, default: 7 },
};

async function renderPanel() {
  await act(async () => {
    root.render(<ShareLinksPanel code="ventas" />);
  });
  await flush();
}

describe("ShareLinksPanel", () => {
  it("renders statuses and meta from GET", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      expect(path).toBe("/api/dashboards/ventas/links");
      return baseState;
    });
    await renderPanel();

    expect(container.textContent).toContain(t.sharing.statusActive);
    expect(container.textContent).toContain(t.sharing.statusExpired);
    expect(container.textContent).toContain(t.sharing.statusRevoked);
    expect(container.textContent).toContain("Para Ana");
    expect(container.textContent).toContain("Revocado");
  });

  it("creates a link and shows the url once", async () => {
    vi.mocked(api.get).mockResolvedValue(baseState);
    vi.mocked(api.post).mockResolvedValue({
      id: 4,
      note: "Para Ana",
      created_by: { id: 2, name: "Luis" },
      created_at: "2026-02-01T08:00:00Z",
      expires_at: "2026-03-03T08:00:00Z",
      revoked_at: null,
      visits: 0,
      last_visit_at: null,
      active: true,
      token: "tok-123",
      url: "https://example.test/s/tok-123",
    });
    await renderPanel();

    await act(async () => {
      byText(t.sharing.dayChip(30))?.click();
    });
    const noteInput = inputByLabel(t.sharing.noteLabel)!;
    typeInto(noteInput, "Para Ana");

    await act(async () => {
      byText(t.sharing.create)?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/dashboards/ventas/links",
      { days: 30, note: "Para Ana" },
    );
    expect(container.textContent).toContain(t.sharing.createdOnce);
    expect(container.textContent).toContain(
      "https://example.test/s/tok-123",
    );
    expect(byText(t.common.copy)).toBeDefined();
  });

  it("revokes after inline confirmation", async () => {
    vi.mocked(api.get).mockResolvedValue(baseState);
    vi.mocked(api.del).mockResolvedValue(undefined);
    await renderPanel();

    expect(document.querySelector('[role="dialog"]')).toBeNull();
    await act(async () => {
      byText(t.sharing.revoke)?.click();
    });
    expect(byText(t.sharing.confirmRevoke)).toBeDefined();
    expect(document.querySelector('[role="dialog"]')).toBeNull();

    await act(async () => {
      byText(t.sharing.confirmRevoke)?.click();
    });
    await flush();

    expect(api.del).toHaveBeenCalledWith(
      "/api/dashboards/ventas/links/1",
    );
  });

  it("hides the creation form when sharing is disabled", async () => {
    vi.mocked(api.get).mockResolvedValue({
      ...baseState,
      sharing_enabled: false,
    });
    await renderPanel();

    expect(container.textContent).toContain(t.sharing.sharingDisabled);
    expect(byText(t.sharing.create)).toBeUndefined();
  });

  it("surfaces 422 days error under the days input", async () => {
    vi.mocked(api.get).mockResolvedValue(baseState);
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(
        422,
        "invalid",
        "Máximo 90 días.",
        { days: "range" },
      ),
    );
    await renderPanel();

    await act(async () => {
      byText(t.sharing.create)?.click();
    });
    await flush();

    const daysInput = inputByLabel(t.sharing.daysLabel)!;
    const describedBy = daysInput.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const errorId = describedBy
      ?.split(" ")
      .find((idPart) => idPart.endsWith("-error"));
    expect(errorId).toBeTruthy();
    expect(document.getElementById(errorId ?? "")?.textContent).toContain(
      "Máximo 90 días.",
    );
  });

  it("uses the server's counted total for the cap", async () => {
    const state = { ...baseState, max_active: 20, active_count: 20 };
    vi.mocked(api.get).mockResolvedValue(state);
    await renderPanel();

    expect(container.textContent).toContain(t.sharing.maxActive(20));
    expect(byText(t.sharing.create)?.disabled).toBe(true);
  });

  it("does not cap when only uncounted subscription links are active", async () => {
    const activeItem = {
      ...baseState.items[0],
      id: 10,
      origin: "subscription" as const,
      counted: false,
    };
    const state = {
      ...baseState,
      max_active: 2,
      active_count: 0,
      items: [activeItem, { ...activeItem, id: 11 }],
    };
    vi.mocked(api.get).mockResolvedValue(state);
    await renderPanel();

    expect(container.textContent).not.toContain(t.sharing.maxActive(2));
    expect(byText(t.sharing.create)?.disabled).toBe(false);
    expect(container.textContent).toContain(t.sharing.origin.subscription);
  });
});
