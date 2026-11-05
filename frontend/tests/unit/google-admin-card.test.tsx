/** Feature 054 (US2…US4): the Seguridad card edits the domains, the provisioning defaults and the
 * ordered rules, and says what the callback will do with them. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GoogleAdminState, GoogleRule } from "../../src/api/types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const initialState = (): GoogleAdminState => ({
  settings: {
    allowed_domains: ["empresa.com"],
    domains_from_env: true,
    auto_provision: false,
    default_role: "user",
    default_access: { mode: "none" },
    apply_rules_to_existing: false,
    updated_at: null,
  },
  dashboards: [
    { code: "cripto", name: "Cripto impacto", status: "published" },
    { code: "salud", name: "Salud", status: "published" },
  ],
});

let state: GoogleAdminState = initialState();

let rules: GoogleRule[] = [
  {
    id: 1, position: 0, condition: "domain", value: ["empresa.com"], role: "admin",
    access: { mode: "all_public" }, enabled: true,
  },
  {
    id: 2, position: 1, condition: "email", value: ["ana@empresa.com"], role: "user",
    access: { mode: "none" }, enabled: true,
  },
];

const saveSettings = vi.fn(async (draft: unknown) => ({
  ...state,
  settings: { ...state.settings, ...(draft as object), domains_from_env: false },
}));
const reorder = vi.fn(async (ids: number[]) =>
  ids.map((id, position) => ({ ...rules.find((r) => r.id === id)!, position })));

vi.mock("../../src/api/google", () => ({
  googleAdmin: {
    state: vi.fn(async () => state),
    rules: vi.fn(async () => rules),
    saveSettings: (draft: unknown) => saveSettings(draft),
    createRule: vi.fn(async () => rules[0]),
    updateRule: vi.fn(async (id: number, body: object) => ({ ...rules[0], id, ...body })),
    deleteRule: vi.fn(async () => undefined),
    reorder: (ids: number[]) => reorder(ids),
  },
}));

vi.mock("../../src/config/BrandingContext", () => ({
  useBranding: () => ({ google_auth: true, telegram_sign_in: false }),
  useBrandingRefresh: () => () => undefined,
}));

import { GoogleAdminCard } from "../../src/components/GoogleAdminCard";
import { t } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  state = initialState();
  rules = [
    { id: 1, position: 0, condition: "domain", value: ["empresa.com"], role: "admin",
      access: { mode: "all_public" }, enabled: true },
    { id: 2, position: 1, condition: "email", value: ["ana@empresa.com"], role: "user",
      access: { mode: "none" }, enabled: true },
  ];
  saveSettings.mockClear();
  reorder.mockClear();
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = null;
  container.remove();
});

async function render() {
  root = createRoot(container);
  await act(async () => root!.render(<GoogleAdminCard />));
  return container;
}

const buttonSaying = (text: string) =>
  Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.trim() === text);

describe("GoogleAdminCard", () => {
  it("shows the domains the policy is using today and where they came from", async () => {
    await render();
    expect(container.textContent).toContain(t.google.admin.title);
    expect(container.textContent).toContain("empresa.com");
    // Until the first save the list is still the deployment's GOOGLE_ALLOWED_DOMAINS.
    expect(container.textContent).toContain(t.google.admin.domains.fromEnv);
  });

  it("saves an added domain", async () => {
    await render();
    const input = container.querySelector<HTMLInputElement>("input[placeholder='empresa.com']")!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value",
      )!.set!;
      setter.call(input, "acme.io");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => buttonSaying(t.google.admin.domains.add)!.click());
    expect(container.textContent).toContain("acme.io");

    await act(async () => buttonSaying(t.common.save)!.click());
    expect(saveSettings).toHaveBeenCalledWith(
      expect.objectContaining({ allowed_domains: ["empresa.com", "acme.io"] }),
    );
  });

  it("reorders the rules by sending the whole list with the new order", async () => {
    await render();
    await act(async () => {
      container.querySelector<HTMLButtonElement>(
        `button[aria-label="${t.google.admin.rules.moveDown}"]`,
      )!.click();
    });
    expect(reorder).toHaveBeenCalledWith([2, 1]);
  });

  it("offers the group condition greyed out as coming soon", async () => {
    await render();
    await act(async () => buttonSaying(t.google.admin.rules.add)!.click());
    const group = container.querySelector<HTMLOptionElement>("option[value='group']")!;
    expect(group.disabled).toBe(true);
    expect(group.textContent).toBe(t.google.admin.rules.conditions.group);
  });

  it("reveals the default role and access only when automatic sign-up is on", async () => {
    await render();
    const picker = () =>
      container.querySelector(`[role="radiogroup"][aria-label="${t.google.admin.provisioning.access}"]`);
    expect(picker()).toBeNull();
    await act(async () => {
      container.querySelector<HTMLElement>(
        `[role="switch"][aria-label="${t.google.admin.provisioning.title}"]`,
      )!.click();
    });
    expect(picker()).not.toBeNull();
  });

  it("reports an env domain it cannot use instead of showing it as policy", async () => {
    await render();
    // Fresh fixture: no rejects, so nothing is said.
    expect(container.textContent).not.toContain("GOOGLE_ALLOWED_DOMAINS trae");

    state = {
      ...state,
      settings: { ...state.settings, allowed_domains: [], domains_rejected: ["https://acme.io;"] },
    };
    await render();
    expect(container.textContent).toContain("GOOGLE_ALLOWED_DOMAINS trae https://acme.io;");
    expect(container.textContent).toContain(t.google.admin.domains.empty);
  });

  it("says the default access is for Usuario accounts", async () => {
    await render();
    await act(async () => {
      container.querySelector<HTMLElement>(
        `[role="switch"][aria-label="${t.google.admin.provisioning.title}"]`,
      )!.click();
    });
    expect(container.textContent).toContain(t.google.admin.provisioning.accessForUsers);
  });

  it("marks a rule an earlier enabled rule already covers", async () => {
    rules = [
      { id: 1, position: 0, condition: "domain", value: ["empresa.com"], role: "admin",
        access: { mode: "none" }, enabled: true },
      { id: 2, position: 1, condition: "domain", value: ["empresa.com"], role: "user",
        access: { mode: "none" }, enabled: true },
      { id: 3, position: 2, condition: "domain", value: ["acme.io"], role: "user",
        access: { mode: "none" }, enabled: true },
    ];
    await render();
    // Only the covered rule carries the hint, named by the position that covers it.
    expect(container.textContent).toContain(t.google.admin.rules.shadowed(1));
    expect(container.textContent).not.toContain(t.google.admin.rules.shadowed(3));
  });

  it("says the provider is off when the installation has no Google client", async () => {
    vi.resetModules();
    // Without the provider the policy is stored but nothing can use it.
    vi.doMock("../../src/config/BrandingContext", () => ({
      useBranding: () => ({ google_auth: false, telegram_sign_in: false }),
      useBrandingRefresh: () => () => undefined,
    }));
    const { GoogleAdminCard: Card } = await import("../../src/components/GoogleAdminCard");
    const fresh = document.createElement("div");
    document.body.appendChild(fresh);
    const local = createRoot(fresh);
    await act(async () => local.render(<Card />));
    expect(fresh.textContent).toContain(t.google.admin.providerOff);
    await act(async () => local.unmount());
    fresh.remove();
  });
});
