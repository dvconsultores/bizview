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
import { SubscriptionsPanel } from "../../src/components/sharing/SubscriptionsPanel";
import { t } from "../../src/i18n/es";
import { formatDateTime } from "../../src/lib/format";

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
const byText = (text: string) =>
  Array.from(container.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === text,
  ) as HTMLButtonElement | undefined;
const buttonContaining = (text: string) =>
  Array.from(container.querySelectorAll("button")).find((b) =>
    b.textContent?.includes(text),
  ) as HTMLButtonElement | undefined;
const inputByLabel = (label: string) => {
  const l = Array.from(container.querySelectorAll("label")).find(
    (x) => x.textContent?.replace("*", "").trim() === label,
  );
  return l
    ? (document.getElementById(l.htmlFor) as HTMLInputElement)
    : null;
};

const def = {
  id: "ventas",
  title: "Ventas",
  description: "",
  icon: null,
  currency: "USD",
  metrics: {},
  dimensions: {},
  periods: {
    default: "last_month",
    allowed: ["yesterday", "last_7_days", "last_month", "custom"],
  },
  compare: { default: "none", allowed: ["none"] },
  filters: [],
  pdf: true,
  ai_narrative: false,
} as const;

const emailOptions = {
  available: true,
  can_link: false,
  allowed_domains: ["acme.com"],
  max_recipients: 20,
  link_days: { min: 1, max: 90, default: 7 },
  items: [],
};

const subscriptionFixture = {
  id: 5,
  frequency: "weekly",
  hour: 8,
  weekday: 0,
  monthday: null,
  period: "last_7_days",
  period_label: "Últimos 7 días",
  attach_pdf: true,
  link_days: null,
  paused: false,
  last_due_at: null,
  next_due_at: "2026-10-12T12:00:00Z",
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
  created_by: { id: 1, name: "Admin" },
  recipients: [{ user_id: 7, name: "Ana Pérez" }, { email: "luis@acme.com" }],
};

async function renderPanel(
  items = [subscriptionFixture],
  extra: { available?: boolean; timezone?: string } = {},
) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.startsWith("/api/dashboards/ventas/email/recipients")) {
      return {
        items: [{ id: 7, name: "Ana Pérez", email: "ana@acme.com" }],
      };
    }
    if (path === "/api/dashboards/ventas/subscriptions") {
      return {
        items,
        available: extra.available ?? true,
        can_link: false,
        timezone: extra.timezone ?? "UTC",
      };
    }
    expect(path).toBe("/api/dashboards/ventas/email");
    return { ...emailOptions, available: extra.available ?? true };
  });
  await act(async () => {
    root.render(<SubscriptionsPanel code="ventas" def={def as never} />);
  });
  await flush();
}

function changeSelect(select: HTMLSelectElement, value: string) {
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!
    .set!.call(select, value);
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("SubscriptionsPanel", () => {
  it("lists subscriptions with schedule and recipients", async () => {
    await renderPanel();

    expect(container.textContent).toContain(
      t.sharing.schedules.everyWeek("lunes", "08:00"),
    );
    expect(container.textContent).toContain("Últimos 7 días");
    expect(container.textContent).toContain(
      t.sharing.schedules.recipientsLine(
        "Ana Pérez, luis@acme.com",
      ),
    );
  });

  it("does not offer custom periods and defaults to the report default", async () => {
    await renderPanel();

    await act(async () => {
      byText(t.sharing.schedules.newSchedule)?.click();
    });

    const periodSelect = inputByLabel(
      t.sharing.schedules.period,
    ) as unknown as HTMLSelectElement;
    expect(periodSelect.value).toBe("last_month");
    expect(
      Array.from(periodSelect.options).some((o) => o.value === "custom"),
    ).toBe(false);
  });

  it("creates a monthly subscription", async () => {
    vi.mocked(api.post).mockResolvedValue(subscriptionFixture);
    await renderPanel();

    await act(async () => {
      byText(t.sharing.schedules.newSchedule)?.click();
    });
    await flush();

    const frequencySelect = inputByLabel(
      t.sharing.schedules.frequency,
    ) as unknown as HTMLSelectElement;
    await act(async () => {
      changeSelect(frequencySelect, "monthly");
    });

    const monthdaySelect = inputByLabel(
      t.sharing.schedules.monthday,
    ) as unknown as HTMLSelectElement;
    const hourSelect = inputByLabel(
      t.sharing.schedules.hour,
    ) as unknown as HTMLSelectElement;
    await act(async () => {
      changeSelect(monthdaySelect, "15");
    });
    await act(async () => {
      changeSelect(hourSelect, "7");
    });
    await act(async () => {
      buttonContaining("Ana Pérez")?.click();
    });

    await act(async () => {
      byText(t.sharing.schedules.save)?.click();
    });
    await flush();

    expect(api.post).toHaveBeenCalledWith(
      "/api/dashboards/ventas/subscriptions",
      {
        frequency: "monthly",
        hour: 7,
        weekday: null,
        monthday: 15,
        period: "last_month",
        attach_pdf: true,
        link_days: null,
        users: [7],
        emails: [],
      },
    );
  });

  it("pauses a subscription", async () => {
    vi.mocked(api.patch).mockResolvedValue(subscriptionFixture);
    await renderPanel();

    await act(async () => {
      byText(t.sharing.schedules.pause)?.click();
    });
    await flush();

    expect(api.patch).toHaveBeenCalledWith(
      "/api/dashboards/ventas/subscriptions/5",
      { paused: true },
    );
  });

  it("deletes only after inline confirmation", async () => {
    vi.mocked(api.del).mockResolvedValue(undefined);
    await renderPanel();

    await act(async () => {
      byText(t.sharing.schedules.delete)?.click();
    });
    expect(api.del).not.toHaveBeenCalled();
    expect(byText(t.sharing.schedules.confirmDelete)).toBeDefined();

    await act(async () => {
      byText(t.sharing.schedules.confirmDelete)?.click();
    });
    await flush();

    expect(api.del).toHaveBeenCalledWith(
      "/api/dashboards/ventas/subscriptions/5",
    );
  });

  it("prefills edit mode and PATCHes recipients", async () => {
    vi.mocked(api.patch).mockResolvedValue(subscriptionFixture);
    await renderPanel();

    await act(async () => {
      byText(t.sharing.schedules.edit)?.click();
    });

    expect(container.textContent).toContain(
      t.sharing.schedules.editSchedule,
    );
    const frequencySelect = inputByLabel(
      t.sharing.schedules.frequency,
    ) as unknown as HTMLSelectElement;
    const weekdaySelect = inputByLabel(
      t.sharing.schedules.weekday,
    ) as unknown as HTMLSelectElement;
    expect(frequencySelect.value).toBe("weekly");
    expect(weekdaySelect.value).toBe("0");
    expect(container.textContent).toContain("Ana Pérez");
    expect(container.textContent).toContain("luis@acme.com");

    await act(async () => {
      byText(t.sharing.schedules.save)?.click();
    });
    await flush();

    expect(api.patch).toHaveBeenCalledWith(
      "/api/dashboards/ventas/subscriptions/5",
      expect.objectContaining({
        users: [7],
        emails: ["luis@acme.com"],
      }),
    );
  });

  it("shows run times in the installation timezone", async () => {
    await renderPanel([subscriptionFixture], { timezone: "America/Caracas" });

    const caracasNext = formatDateTime(
      subscriptionFixture.next_due_at,
      "America/Caracas",
    );
    const tokyoNext = formatDateTime(subscriptionFixture.next_due_at, "Asia/Tokyo");

    expect(container.textContent).toContain(
      t.sharing.schedules.nextRun(caracasNext),
    );
    expect(container.textContent).toContain(
      t.sharing.schedules.timezoneNote("America/Caracas"),
    );
    expect(caracasNext).not.toBe(tokyoNext);
  });

  it("stays usable for pause and delete when email is off", async () => {
    await renderPanel([subscriptionFixture], { available: false });

    expect(container.textContent).toContain(t.sharing.email.unavailable);
    expect(byText(t.sharing.schedules.newSchedule)).toBeUndefined();
    expect(byText(t.sharing.schedules.edit)).toBeUndefined();

    vi.mocked(api.patch).mockResolvedValue({ ...subscriptionFixture, paused: true });
    await act(async () => {
      byText(t.sharing.schedules.pause)?.click();
    });
    await flush();
    expect(vi.mocked(api.patch)).toHaveBeenCalledWith(
      "/api/dashboards/ventas/subscriptions/5",
      { paused: true },
    );

    vi.mocked(api.del).mockResolvedValue(undefined);
    await act(async () => {
      byText(t.sharing.schedules.delete)?.click();
    });
    await act(async () => {
      byText(t.sharing.schedules.confirmDelete)?.click();
    });
    await flush();
    expect(vi.mocked(api.del)).toHaveBeenCalledWith(
      "/api/dashboards/ventas/subscriptions/5",
    );
  });
});

describe("SubscriptionsPanel owned by a project (feature 020)", () => {
  it("links the project, labels roles and only offers pause/resume", async () => {
    const { MemoryRouter } = await import("react-router");
    const owned = {
      ...subscriptionFixture,
      recipients: [{ role: "admin" }],
      managed_by: { project: "Ventas Caracas", slug: "ventas-caracas", distribution: "envio" },
    };
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/dashboards/ventas/subscriptions") {
        return { items: [owned], available: true, can_link: false, timezone: "UTC" };
      }
      return { ...emailOptions };
    });
    await act(async () => {
      root.render(
        <MemoryRouter>
          <SubscriptionsPanel code="ventas" def={def as never} />
        </MemoryRouter>,
      );
    });
    await flush();

    const link = Array.from(container.querySelectorAll("a")).find((a) =>
      a.textContent?.includes(t.sharing.schedules.managedBy("Ventas Caracas")),
    );
    expect(link?.getAttribute("href")).toBe("/proyectos/ventas-caracas");
    expect(container.textContent).toContain(
      t.sharing.schedules.recipientsLine(t.sharing.schedules.roleRecipient(t.roles.admin)),
    );
    expect(byText(t.sharing.schedules.edit)).toBeUndefined();
    expect(byText(t.sharing.schedules.delete)).toBeUndefined();
    expect(byText(t.sharing.schedules.pause)).toBeDefined();
  });
});
