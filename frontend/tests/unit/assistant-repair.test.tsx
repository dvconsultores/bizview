/** Feature 036: a conversation that cannot be replayed says so and offers the repair. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AssistantSession } from "../../src/api/types";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const repaired: AssistantSession = {
  id: 23,
  title: "CoinmarketCap",
  status: "open",
  mode: "auto",
  messages: [
    { id: 1, role: "user", content: "continua", created_at: "2026-10-26T13:25:00Z" },
    { id: 2, role: "assistant", content: "", created_at: "2026-10-26T13:25:01Z" },
  ],
} as AssistantSession;

vi.mock("../../src/api/client", () => ({
  api: {
    get: vi.fn(async () => repaired),
    post: vi.fn(async () => ({ call_ids: 0, paired: 3, orphans: 1, replayable: true })),
    patch: vi.fn(),
    del: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  },
  askReauth: vi.fn(async () => true),
  qs: () => "",
}));
vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ ai_enabled: true, vision_enabled: true,
                        attachments_max_mb: 5, attachments_max_per_message: 4 }),
}));
vi.mock("../../src/auth/AuthContext", () => ({
  useOptionalUser: () => ({ attachments_notice_at: "2026-01-01T00:00:00Z" }),
}));
vi.mock("../../src/api/attachments", () => ({
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
  acceptAttachmentsNotice: vi.fn(),
}));

import { api } from "../../src/api/client";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

const broken: AssistantSession = {
  ...repaired,
  messages: [
    { id: 1, role: "user", content: "continua", created_at: "2026-10-26T13:25:00Z" },
    {
      id: 2,
      role: "assistant",
      content: "La conversación guardada no se puede reenviar al proveedor.",
      created_at: "2026-10-26T13:25:01Z",
      error: {
        code: "history_invalid",
        detail: "tool_use_id call_00_g9JN not found",
        provider: "anthropic",
        model: "deepseek-flash",
        at: "2026-10-26T13:25:01Z",
        request_id: "a1b2c3d4",
        action: null,
        blocked: false,
      },
    },
  ],
} as AssistantSession;

async function render(session: AssistantSession) {
  await act(async () => {
    root?.render(
      <MemoryRouter>
        <AssistantChat session={session} onSession={() => {}} />
      </MemoryRouter>,
    );
  });
  await act(async () => {});
}

const buttonWith = (text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent?.includes(text));

describe("repairing a conversation (feature 036)", () => {
  it("explains the problem and offers the repair", async () => {
    await render(broken);
    expect(container.textContent).toContain(t.ai.historyInvalidHint);
    expect(buttonWith(t.ai.repair)).toBeTruthy();
  });

  it("repairs through the endpoint and reloads the conversation", async () => {
    await render(broken);
    await act(async () => buttonWith(t.ai.repair)!.click());
    await act(async () => {});

    expect(vi.mocked(api.post)).toHaveBeenCalledWith("/api/assistant/sessions/23/repair", {});
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/assistant/sessions/23");
    expect(container.textContent).toContain(t.ai.repairDone(3, 1));
  });

  it("never offers the repair for an ordinary provider failure", async () => {
    const other = {
      ...broken,
      messages: [
        broken.messages[0],
        {
          ...broken.messages[1],
          error: { ...broken.messages[1].error!, code: "no_credit", action: "admin_ai" },
        },
      ],
    } as AssistantSession;
    await render(other);
    expect(buttonWith(t.ai.repair)).toBeUndefined();
    const link = [...container.querySelectorAll("a")].find((a) =>
      a.textContent?.includes(t.ai.action.admin_ai));
    expect(link?.getAttribute("href")).toBe("/admin/ia");
  });
});
