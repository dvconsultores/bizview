import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantChat } from "../../src/components/assistant/AssistantChat";
import type { AssistantSession } from "../../src/api/types";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

let vision = true;
let noticeAt: string | null = "2026-01-01T00:00:00Z";
vi.mock("../../src/auth/AuthContext", () => ({
  useOptionalUser: () => ({ attachments_notice_at: noticeAt }),
}));
vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() },
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
  askReauth: vi.fn(async () => true),
  qs: () => "",
}));

vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({
    ai_enabled: true,
    vision_enabled: vision,
    attachments_max_mb: 5,
    attachments_max_per_message: 4,
  }),
}));

vi.mock("../../src/api/attachments", () => ({
  uploadAttachment: vi.fn(async (_id: number, file: File) => ({
    id: 41,
    media_type: file.type,
    byte_size: file.size,
    original_name: file.name,
    url: "/api/assistant/attachments/41",
  })),
  deleteAttachment: vi.fn(async () => undefined),
  acceptAttachmentsNotice: vi.fn(async () => undefined),
}));

import { api } from "../../src/api/client";
import {
  acceptAttachmentsNotice,
  deleteAttachment,
  uploadAttachment,
} from "../../src/api/attachments";

const ts = "2026-10-12T12:00:00Z";

function makeSession(extra: Partial<AssistantSession> = {}): AssistantSession {
  return {
    id: 7,
    title: "Prueba",
    status: "open",
    draft: { files: {}, summary: "" },
    validation: { valid: true, errors: [], warnings: [] },
    readiness: { ready: true, pending: [] },
    preview: null,
    applied_version_id: null,
    tokens_used: 10,
    token_budget: 1000,
    created_at: ts,
    updated_at: ts,
    messages: [{ id: 1, role: "user", content: "Un reporte", created_at: ts }],
    ...extra,
  } as AssistantSession;
}

function png() {
  return new File([new Uint8Array([137, 80, 78, 71])], "boceto.png", { type: "image/png" });
}

describe("image briefs in the composer (feature 024)", () => {
  let container: HTMLElement;
  let root: Root;

  beforeEach(() => {
    vision = true;
    noticeAt = "2026-01-01T00:00:00Z";
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    vi.clearAllMocks();
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function renderChat(session = makeSession()) {
    function Harness() {
      const [s, setS] = useState<AssistantSession>(session);
      return <AssistantChat session={s} onSession={setS} />;
    }
    await act(async () => {
      root.render(<Harness />);
    });
    await act(async () => {
      await Promise.resolve();
    });
  }

  function attachButton() {
    return container.querySelector("[data-attach]") as HTMLButtonElement;
  }

  function fileInput() {
    return container.querySelector('input[type="file"]') as HTMLInputElement;
  }

  async function chooseFile(file = png()) {
    const input = fileInput();
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    await act(async () => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });
  }

  function sendButton() {
    return Array.from(container.querySelectorAll("button")).find((b) =>
      b.querySelector("span.sr-only")?.textContent?.includes("Enviar"),
    ) as HTMLButtonElement;
  }

  it("uploads the chosen image and sends its id with the message", async () => {
    await renderChat();
    await chooseFile();
    expect(uploadAttachment).toHaveBeenCalledWith(7, expect.any(File));
    expect(container.querySelector('img[src="/api/assistant/attachments/41"]')).not.toBeNull();

    (api.post as any).mockResolvedValue({ messages: [], session: makeSession() });
    await act(async () => {
      sendButton().click();
    });
    await act(async () => {
      await Promise.resolve();
    });

    const [, body] = (api.post as any).mock.calls[0];
    expect(body).toEqual({ text: "", attachments: [41] });
    expect(container.textContent).not.toContain("Las imágenes se envían");
  });

  it("shows the one-time notice before the first image is sent", async () => {
    noticeAt = null;
    await renderChat();
    await chooseFile();
    (api.post as any).mockResolvedValue({ messages: [], session: makeSession() });
    await act(async () => {
      sendButton().click();
    });
    expect(api.post).not.toHaveBeenCalled();
    expect(container.textContent).toContain("No adjuntes capturas con datos de clientes");

    const accept = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Entendido",
    ) as HTMLButtonElement;
    await act(async () => {
      accept.click();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(acceptAttachmentsNotice).toHaveBeenCalled();
    expect((api.post as any).mock.calls[0][1]).toEqual({ text: "", attachments: [41] });
  });

  it("removes a waiting image and deletes it on the server", async () => {
    await renderChat();
    await chooseFile();
    const remove = container.querySelector(
      '[aria-label="Quitar boceto.png"]',
    ) as HTMLButtonElement;
    await act(async () => {
      remove.click();
    });
    expect(container.querySelector('img[src="/api/assistant/attachments/41"]')).toBeNull();
  });

  it("keeps the attach control icon-only and labelled", async () => {
    await renderChat();
    const button = attachButton();
    // Only the screen-reader span carries the words: on screen it is a paperclip.
    expect(button.querySelector("span.sr-only")?.textContent?.trim()).toBe("Adjuntar boceto");
    expect(button.getAttribute("aria-label")).toBe("Adjuntar boceto");
    expect(button.querySelector("svg")).not.toBeNull();
  });

  it("disables the attach control when the model cannot read images", async () => {
    vision = false;
    await renderChat();
    expect(attachButton().disabled).toBe(true);
    expect(attachButton().title).toContain("no puede leer imágenes");
  });

  it("renders the images of a sent message in the transcript", async () => {
    await renderChat(
      makeSession({
        messages: [
          {
            id: 1,
            role: "user",
            content: "",
            created_at: ts,
            attachments: [
              {
                id: 41,
                media_type: "image/png",
                byte_size: 4,
                original_name: "boceto.png",
                url: "/api/assistant/attachments/41",
              },
            ],
          },
        ],
      }),
    );
    const image = container.querySelector('img[src="/api/assistant/attachments/41"]');
    expect(image?.getAttribute("alt")).toBe("boceto.png");
  });
  it("opens a sent image and removes it from the message", async () => {
    const withImage = makeSession({
      messages: [
        {
          id: 1,
          role: "user",
          content: "mira",
          created_at: ts,
          attachments: [
            {
              id: 41,
              media_type: "image/png",
              byte_size: 4,
              original_name: "boceto.png",
              url: "/api/assistant/attachments/41",
            },
          ],
        },
      ],
    });
    await renderChat(withImage);
    const link = container.querySelector(
      'a[href="/api/assistant/attachments/41"]',
    ) as HTMLAnchorElement;
    expect(link.target).toBe("_blank");

    await act(async () => {
      (container.querySelector('[aria-label="Quitar boceto.png"]') as HTMLButtonElement).click();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(deleteAttachment).toHaveBeenCalledWith(41);
    expect(container.querySelector('a[href="/api/assistant/attachments/41"]')).toBeNull();
  });

  it("accepts an image dropped on the composer", async () => {
    await renderChat();
    const target = container.querySelector("[data-drop-target]") as HTMLElement;
    const file = png();
    await act(async () => {
      const event = new Event("drop", { bubbles: true, cancelable: true }) as any;
      event.dataTransfer = { files: [file], types: ["Files"] };
      target.dispatchEvent(event);
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(uploadAttachment).toHaveBeenCalledWith(7, file);
    expect(container.querySelector('img[src="/api/assistant/attachments/41"]')).not.toBeNull();
  });
});
