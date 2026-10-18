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

import { api } from "../../src/api/client";
import { EmailSendPanel } from "../../src/components/sharing/EmailSendPanel";
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

const selection = {
  period: "last_month",
  from: "",
  to: "",
  compare: "none",
  filters: { brand: ["Acme"] },
} as const;

const baseOptions = {
  available: true,
  can_link: false,
  allowed_domains: ["acme.com"],
  max_recipients: 20,
  link_days: { min: 1, max: 90, default: 7 },
  items: [],
};

async function renderPanel(overrides: Partial<typeof baseOptions> = {}) {
  const options = { ...baseOptions, ...overrides };
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.startsWith("/api/dashboards/ventas/email/recipients")) {
      return { items: [{ id: 7, name: "Ana Pérez" }] };
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

describe("EmailSendPanel", () => {
  it("shows unavailable and no send button when email is off", async () => {
    await renderPanel({ available: false });

    expect(container.textContent).toContain(t.sharing.email.unavailable);
    expect(byText(t.sharing.email.send)).toBeUndefined();
  });

  it("validates empty recipients without POSTing", async () => {
    await renderPanel();

    await act(async () => {
      byText(t.sharing.email.send)?.click();
    });
    await flush();

    expect(container.textContent).toContain(
      t.sharing.email.noRecipients,
    );
    expect(api.post).not.toHaveBeenCalled();
  });

  it("rejects external domains not in the allowed list", async () => {
    await renderPanel();

    const externalInput = inputByLabel(t.sharing.email.external)!;
    typeInto(externalInput, "x@other.com");
    await act(async () => {
      byText(t.sharing.email.add)?.click();
    });

    expect(container.textContent).toContain(
      t.sharing.email.domainNotAllowed(["acme.com"]),
    );
    expect(container.textContent).not.toContain("x@other.com");
  });

  it("sends with recipients, subject and current selection", async () => {
    const queuedSend = {
      id: 11,
      subject: "Cierre",
      status: "queued",
      created_at: "2026-02-01T08:00:00Z",
      finished_at: null,
      attach_pdf: true,
      link_days: null,
      subscription_id: null,
      requested_by: { id: 2, name: "Luis" },
      deliveries: [],
    };
    vi.mocked(api.post).mockResolvedValue(queuedSend);
    await renderPanel();

    await act(async () => {
      byText("Ana Pérez")?.click();
    });
    const externalInput = inputByLabel(t.sharing.email.external)!;
    typeInto(externalInput, "luis@acme.com");
    await act(async () => {
      byText(t.sharing.email.add)?.click();
    });
    typeInto(inputByLabel(t.sharing.email.subject)!, "Cierre");

    await act(async () => {
      byText(t.sharing.email.send)?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/dashboards/ventas/email",
      {
        users: [7],
        emails: ["luis@acme.com"],
        subject: "Cierre",
        message: null,
        selection: {
          period: "last_month",
          compare: "none",
          "filter.brand": ["Acme"],
        },
        attach_pdf: true,
        link_days: null,
      },
    );
    expect(container.textContent).toContain("Cierre");
    expect(container.textContent).toContain(
      t.sharing.email.sendStatus.queued,
    );
  });

  it("shows link days only when can_link and sends the default", async () => {
    const options = {
      ...baseOptions,
      can_link: true,
      items: [
        {
          id: 1,
          subject: "Anterior",
          status: "sent",
          created_at: "2026-01-01T08:00:00Z",
          finished_at: "2026-01-01T08:01:00Z",
          attach_pdf: true,
          link_days: null,
          subscription_id: null,
          requested_by: null,
          deliveries: [],
        },
      ],
    };
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path.startsWith("/api/dashboards/ventas/email/recipients")) {
        return { items: [{ id: 7, name: "Ana Pérez" }] };
      }
      expect(path).toBe("/api/dashboards/ventas/email");
      return options;
    });
    vi.mocked(api.post).mockResolvedValue(options.items[0]);
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

    expect(inputByLabel(t.sharing.email.linkDays)).toBeNull();

    await act(async () => {
      const checkbox = Array.from(
        container.querySelectorAll('input[type="checkbox"]'),
      ).find((input) =>
        input.closest("label")?.textContent?.includes(
          t.sharing.email.includeLink,
        ),
      ) as HTMLInputElement | undefined;
      checkbox?.click();
    });

    expect(inputByLabel(t.sharing.email.linkDays)).not.toBeNull();

    await act(async () => {
      byText("Ana Pérez")?.click();
    });
    await act(async () => {
      byText(t.sharing.email.send)?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/dashboards/ventas/email",
      expect.objectContaining({ link_days: 7 }),
    );
  });

  it("shows delivery errors on listed sends", async () => {
    await renderPanel({
      items: [
        {
          id: 8,
          subject: "Falló",
          status: "failed",
          created_at: "2026-02-01T08:00:00Z",
          finished_at: "2026-02-01T08:01:00Z",
          attach_pdf: true,
          link_days: null,
          subscription_id: null,
          requested_by: null,
          deliveries: [
            {
              id: 9,
              recipient: "ana@acme.com",
              user_id: null,
              status: "failed",
              attempts: 2,
              error: "El buzón está lleno.",
              sent_at: null,
            },
          ],
        },
      ] as never,
    });

    expect(container.textContent).toContain("El buzón está lleno.");
    expect(container.textContent).toContain(
      t.sharing.email.attempts(2),
    );
  });

  it("prefills the subject with the dashboard name and resets it after sending", async () => {
    vi.mocked(api.post).mockResolvedValue({
      id: 11,
      subject: "Cierre",
      status: "queued",
      created_at: "2026-02-01T08:00:00Z",
      finished_at: null,
      attach_pdf: true,
      link_days: null,
      subscription_id: null,
      requested_by: { id: 2, name: "Luis" },
      deliveries: [],
    });
    await renderPanel();
    const subjectInput = inputByLabel(t.sharing.email.subject)!;
    expect(subjectInput.value).toBe("Ventas");

    typeInto(subjectInput, "Cierre");
    await act(async () => {
      byText("Ana Pérez")?.click();
    });
    await act(async () => {
      byText(t.sharing.email.send)?.click();
    });
    await flush();

    expect(vi.mocked(api.post)).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ subject: "Cierre" }),
    );
    expect(subjectInput.value).toBe("Ventas");
  });

  it("disables Incluir enlace at the link cap", async () => {
    await renderPanel({ can_link: true, links_active: 20, links_max: 20 } as never);
    const label = Array.from(container.querySelectorAll("label")).find(
      (l) => l.textContent?.trim() === t.sharing.email.includeLink,
    );
    expect(label?.querySelector("input")?.disabled).toBe(true);
    expect(container.textContent).toContain(t.sharing.email.linkCapReached(20));
  });
});
