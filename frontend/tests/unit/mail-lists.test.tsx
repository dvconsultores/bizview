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
  qs: (p: Record<string, string | number | undefined | null>) => {
    const parts = Object.entries(p)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
    return parts.length ? `?${parts.join("&")}` : "";
  },
}));

import { api } from "../../src/api/client";
import { EmailSendPanel } from "../../src/components/sharing/EmailSendPanel";
import { Lists } from "../../src/pages/mail/Lists";
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
const byLabel = (label: string) =>
  Array.from(container.querySelectorAll("button")).find(
    (b) => b.getAttribute("aria-label") === label,
  ) as HTMLButtonElement | undefined;
const inputByLabel = (label: string) => {
  const l = Array.from(container.querySelectorAll("label")).find(
    (x) => x.textContent?.replace("*", "").trim() === label,
  );
  return l ? (document.getElementById(l.htmlFor) as HTMLInputElement | null) : null;
};

const selection = {
  period: "last_month",
  from: "",
  to: "",
  compare: "none",
  filters: {},
} as const;

const listOption = {
  id: 7,
  name: "Gerencia comercial",
  count: 14,
  visibility: "compartida",
  kind: "members",
  role: null,
};

const baseOptions = {
  available: true,
  can_link: false,
  allowed_domains: [] as string[],
  max_recipients: null,
  free_addresses_role: "user",
  sending_paused: false,
  lists: [listOption],
  link_days: { min: 1, max: 90, default: 7 },
  items: [],
};

async function renderPanel(overrides: Record<string, unknown> = {}) {
  const options = { ...baseOptions, ...overrides };
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.startsWith("/api/dashboards/ventas/email/recipients")) {
      return { items: [{ id: 3, name: "Ana Pérez" }] };
    }
    expect(path).toBe("/api/dashboards/ventas/email");
    return options;
  });
  await act(async () => {
    root.render(
      <EmailSendPanel
        code="ventas"
        dashboardName="Ventas"
        selection={selection as never}
        pdfAvailable={true}
      />,
    );
  });
  await flush();
}

const send = () =>
  Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === t.sharing.email.send,
  ) as HTMLButtonElement | undefined;

describe("mailing lists in the send panel", () => {
  it("counts users, the people in each chosen list and the typed addresses", async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 21, deliveries: [] });
    await renderPanel();

    await act(async () => {
      byLabel(t.sharing.email.addList("Gerencia comercial"))?.click();
    });
    await act(async () => {
      byText("Ana Pérez")?.click();
    });
    typeInto(inputByLabel(t.sharing.email.external)!, "luis@cliente.com");
    await act(async () => {
      byText(t.sharing.email.add)?.click();
    });

    expect(container.textContent).toContain(t.sharing.email.recipientCount(16));

    await act(async () => {
      send()?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/dashboards/ventas/email",
      expect.objectContaining({
        users: [3],
        lists: [7],
        emails: ["luis@cliente.com"],
      }),
    );
  });

  it("renders a list chip with its name and how many people it reaches", async () => {
    await renderPanel();

    expect(container.textContent).toContain(
      t.sharing.email.listChip("Gerencia comercial", 14),
    );

    await act(async () => {
      byLabel(t.sharing.email.addList("Gerencia comercial"))?.click();
    });

    // The chip in the recipient box repeats the same words and offers its own removal.
    expect(byLabel(t.sharing.email.removeList("Gerencia comercial"))).toBeDefined();
    expect(container.textContent).toContain(t.sharing.email.listChip("Gerencia comercial", 14));
  });

  it("turns a pasted Nombre <correo> into a chip", async () => {
    await renderPanel();

    const paste = inputByLabel(t.sharing.email.paste)!;
    typeInto(paste, "Luis Pérez <luis@cliente.com>; ana@cliente.com");
    await act(async () => {
      byText(t.sharing.email.pasteButton)?.click();
    });

    expect(container.textContent).toContain("luis@cliente.com");
    expect(container.textContent).toContain("ana@cliente.com");
    expect(container.textContent).toContain(t.sharing.email.recipientCount(2));
    expect(container.textContent).not.toContain(t.sharing.email.invalidAddress);
  });

  it("shows an invalid address in red and blocks the send", async () => {
    await renderPanel();

    const paste = inputByLabel(t.sharing.email.paste)!;
    typeInto(paste, "no-es-un-correo");
    await act(async () => {
      byText(t.sharing.email.pasteButton)?.click();
    });

    expect(container.textContent).toContain("no-es-un-correo");
    expect(container.textContent).toContain(t.sharing.email.invalidAddress);
    expect(container.textContent).toContain(t.sharing.email.invalidAddresses(1));

    await act(async () => {
      send()?.click();
    });
    await flush();

    expect(api.post).not.toHaveBeenCalled();
  });

  it("says the send is queued when sending is paused", async () => {
    await renderPanel({ sending_paused: true });

    expect(container.textContent).toContain(t.sharing.email.sendingPaused);
    expect(send()).toBeDefined();
  });

  it("renders the history with masked addresses and re-sends the failed ones", async () => {
    const failedSend = {
      id: 8,
      subject: "Cierre de octubre",
      status: "partial",
      created_at: "2026-11-01T08:00:00Z",
      finished_at: "2026-11-01T08:01:00Z",
      attach_pdf: true,
      link_days: null,
      subscription_id: null,
      requested_by: { id: 2, name: "Luis" },
      kinds: { users: 1, lists: ["Gerencia comercial"], emails: 1, total: 3 },
      count: 3,
      deliveries: [
        {
          id: 9,
          recipient: "a***@cliente.com",
          user_id: null,
          list_id: null,
          status: "failed",
          attempts: 2,
          error: "El buzón está lleno.",
          sent_at: null,
        },
      ],
    };
    vi.mocked(api.post).mockResolvedValue({ ...failedSend, id: 30, deliveries: [] });
    await renderPanel({ items: [failedSend] });

    expect(container.textContent).toContain("a***@cliente.com");
    expect(container.textContent).toContain("El buzón está lleno.");
    expect(container.textContent).toContain(
      t.sharing.email.kinds.lists("Gerencia comercial"),
    );

    const resend = Array.from(container.querySelectorAll("button")).find((b) =>
      b.textContent?.includes(t.sharing.email.resendFailed),
    );
    await act(async () => {
      resend?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/dashboards/ventas/email/sends/8/resend-failed",
    );
  });
});

const listFixture = {
  id: 7,
  name: "Gerencia comercial",
  description: "Comerciales activos",
  visibility: "compartida",
  kind: "members",
  role: null,
  owner: { id: 3, name: "Ana Pérez" },
  mine: true,
  editable: true,
  count: 2,
  paused: 0,
  created_at: "2026-11-06T10:00:00Z",
  updated_at: "2026-11-06T10:00:00Z",
};

describe("the lists page", () => {
  async function renderLists() {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/mail/lists/7") {
        return {
          ...listFixture,
          members: [
            { id: 31, address: "ana@cliente.com", name: "Ana", paused: false },
            { id: 32, address: "luis@cliente.com", name: null, paused: true },
          ],
        };
      }
      expect(path).toBe("/api/mail/lists?scope=all");
      return { items: [listFixture], can_share: false, max_members: 1000 };
    });
    await act(async () => {
      root.render(<MemoryRouter><Lists /></MemoryRouter>);
    });
    await flush();
  }

  it("carries the standard back control to Administración (061)", async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], can_share: true, max_members: 1000 });
    await act(async () => {
      root.render(<MemoryRouter><Lists admin /></MemoryRouter>);
    });
    await act(async () => { await Promise.resolve(); });
    const back = container.querySelector<HTMLAnchorElement>('a[href="/admin"]');
    expect(back).not.toBeNull();
    expect(back!.textContent).toContain(t.common.back);
  });

  it("renders the members and pauses one through the API", async () => {
    vi.mocked(api.post).mockResolvedValue({
      ...listFixture,
      members: [
        { id: 31, address: "ana@cliente.com", name: "Ana", paused: true },
        { id: 32, address: "luis@cliente.com", name: null, paused: true },
      ],
    });
    await renderLists();

    expect(container.textContent).toContain("Gerencia comercial");
    expect(container.textContent).toContain(
      t.mailLists.count(2, 1000),
    );

    await act(async () => {
      byText(t.mailLists.open)?.click();
    });
    await flush();

    expect(container.textContent).toContain("ana@cliente.com");
    expect(container.textContent).toContain("luis@cliente.com");

    await act(async () => {
      byLabel(t.mailLists.pauseMember("ana@cliente.com"))?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/mail/lists/7/members/31/pause",
      { paused: true },
    );
  });

  it("shows the empty state when there are no lists", async () => {
    vi.mocked(api.get).mockResolvedValue({
      items: [],
      can_share: false,
      max_members: 1000,
    });
    await act(async () => {
      root.render(<MemoryRouter><Lists /></MemoryRouter>);
    });
    await flush();

    expect(container.textContent).toContain(t.mailLists.empty);
  });
});
