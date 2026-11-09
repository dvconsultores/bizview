/** Feature 059: the phone-sized sign-in screen. jsdom has no layout engine, so the geometry itself
 * is asserted in `tests/e2e/mobile-first.spec.ts`; here the classes and the structure that produce
 * it are pinned, plus the markup a screen reader and a keyboard see. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
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
  qs: () => "",
}));

const branding = {
  product_name: "Bizview",
  organization_name: "Consultores",
  logo_url: null,
  version: "0.2.0",
  source_url: null,
  license: "AGPL-3.0-or-later",
  ai_enabled: false,
  telegram_sign_in: false,
  telegram_bot: null,
  google_auth: false,
};

const auth = {
  user: null,
  loading: false,
  login: vi.fn(),
  completeMfa: vi.fn(),
  logout: vi.fn(),
  refresh: vi.fn(),
  setUser: vi.fn(),
};

vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => auth,
  MFA_SETUP_PATH: "/seguridad/doble-factor",
  safeNext: (next: string | null) =>
    !next || !next.startsWith("/") || next.startsWith("//") ? "/" : next,
}));
vi.mock("../../src/config/BrandingContext", () => ({ useBranding: () => branding }));
vi.mock("../../src/components/Toast", () => ({ useToast: () => vi.fn() }));
vi.mock("../../src/theme/ThemeContext", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../src/theme/ThemeContext")>()),
  useTheme: () => ({
    resolved: "light",
    preference: "system",
    setPreference: async () => undefined,
    palette: "impacto",
    tokens: {},
    setPalette: () => undefined,
  }),
}));

import { LocaleProvider } from "../../src/i18n";
import { es } from "../../src/i18n/es";
import { SignIn } from "../../src/pages/SignIn";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  branding.google_auth = false;
  branding.telegram_sign_in = false;
  localStorage.clear();
  localStorage.setItem("bizview.locale", "es");
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  root = null;
  container.remove();
});

async function render() {
  await act(async () => {
    root!.render(
      <MemoryRouter initialEntries={["/ingresar"]}>
        <LocaleProvider>
          <Routes>
            <Route path="/ingresar" element={<SignIn />} />
          </Routes>
        </LocaleProvider>
      </MemoryRouter>,
    );
  });
}

const buttons = () => Array.from(container.querySelectorAll("button"));
const byText = (text: string) =>
  buttons().find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

describe("sign-in on a phone", () => {
  it("fits one screen: dvh root, no negative margin and a compact hero", async () => {
    await render();
    const page = container.firstElementChild as HTMLElement;
    expect(page.className).toContain("min-h-dvh");
    // The card no longer overlaps the banner (`-mt-8` was the overlap the report caught).
    expect(container.innerHTML).not.toContain("-mt-8");
    const main = container.querySelector("main") as HTMLElement;
    expect(main.className).toContain("pt-4");
    const card = main.firstElementChild as HTMLElement;
    expect(card.className).toContain("w-full");
    expect(card.className).toContain("p-4");
  });

  it("keeps the language switch below the header instead of over the product name", async () => {
    await render();
    const group = container.querySelector('[role="radiogroup"]') as HTMLElement;
    expect(group).not.toBeNull();
    // The compact toggle sits in the hero's own flow, right aligned, never over the product name.
    const row = group.parentElement as HTMLElement;
    expect(row.className).toContain("justify-end");
    expect(row.className).not.toContain("absolute");
    const hero = row.parentElement as HTMLElement;
    expect(hero.textContent).toContain(branding.product_name);
  });

  it("shows the tagline only when the viewport is tall enough and hides it on the smallest", async () => {
    await render();
    const tagline = Array.from(container.querySelectorAll("p")).find(
      (p) => p.textContent === es.signIn.heroTagline,
    ) as HTMLElement;
    expect(tagline.className).toContain("[@media(min-height:600px)]:block");
    expect(tagline.className).toContain("hidden");
  });

  it("sets the autocomplete hints the password managers expect", async () => {
    await render();
    const email = container.querySelector<HTMLInputElement>('input[type="email"]')!;
    const password = container.querySelector<HTMLInputElement>('input[type="password"]')!;
    expect(email.getAttribute("autocomplete")).toBe("email");
    expect(password.getAttribute("autocomplete")).toBe("current-password");
    // 44 px under a finger, the desktop height above it (`Input`/`PasswordField` share the rule).
    expect(email.className).toContain("max-sm:min-h-tap");
  });

  it("stacks both providers, one full-width button per row, with the full labels", async () => {
    // Feature 062: 059 had put the two side by side on a phone with short labels; the owner reversed
    // it, and the test is the record of the decision. Two buttons a thumb apart with abbreviated
    // names are harder to tell apart than two rows of one.
    branding.google_auth = true;
    branding.telegram_sign_in = true;
    await render();
    const google = container.querySelector('[data-testid="google-sign-in"]') as HTMLButtonElement;
    const telegram = Array.from(container.querySelectorAll("button")).find(
      (button) => button.getAttribute("aria-label") === es.telegram.signIn,
    )!;
    expect(google).not.toBeNull();
    expect(telegram).toBeDefined();
    const row = google.parentElement as HTMLElement;
    expect(row.className).not.toContain("grid");
    expect(row.className).toContain("space-y-3");
    expect(row.contains(telegram)).toBe(true);
    // The full sentence at every width, and 48 px of target for a thumb.
    expect(google.textContent).toBe(es.google.signIn);
    expect(telegram.textContent).toBe(es.telegram.signIn);
    for (const button of [google, telegram]) {
      expect(button.className).toContain("w-full");
      // 48 px, in px units (`min-h-tap` is 44 and would be the floor, not the intent).
      expect(button.className).toMatch(/min-h-\[48px\]|min-h-tap/);
    }
  });

  it("gives a lone provider the whole width", async () => {
    branding.google_auth = true;
    await render();
    const google = container.querySelector('[data-testid="google-sign-in"]') as HTMLButtonElement;
    const row = google.parentElement as HTMLElement;
    expect(row.className).not.toContain("grid-cols-2");
    expect(google.textContent).toBe(es.google.signIn);
  });

  it("reports a failed sign-in inside the card, not as a banner that pushes the form", async () => {
    const { ApiError } = await import("../../src/api/client");
    auth.login.mockRejectedValue(new ApiError(401, "invalid_credentials", "Credenciales inválidas"));
    await render();
    const email = container.querySelector<HTMLInputElement>('input[type="email"]')!;
    const password = container.querySelector<HTMLInputElement>('input[type="password"]')!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(email, "ana@example.com");
      email.dispatchEvent(new Event("input", { bubbles: true }));
      setter.call(password, "secreta");
      password.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => {
      (container.querySelector("form") as HTMLFormElement).requestSubmit();
      await Promise.resolve();
    });
    const card = container.querySelector("main")!.firstElementChild as HTMLElement;
    // Inline, inside the card: no page-level banner pushing the form down.
    expect(card.textContent).toContain(es.signIn.invalid);
  });
});
