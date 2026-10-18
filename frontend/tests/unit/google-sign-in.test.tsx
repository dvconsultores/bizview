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
  qs: (p: Record<string, string | number | undefined | null>) => {
    const parts = Object.entries(p)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
    return parts.length ? `?${parts.join("&")}` : "";
  },
}));

// Feature 027: the installation's public config decides whether the Google action exists.
const branding = {
  product_name: "Bizview AI Powered",
  organization_name: "",
  logo_url: null,
  version: "0.1.0",
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

import { en } from "../../src/i18n/en";
import { es } from "../../src/i18n/es";
import { LocaleProvider } from "../../src/i18n";
import { SignIn } from "../../src/pages/SignIn";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  branding.google_auth = false;
  branding.telegram_sign_in = false;
  auth.login.mockReset();
  auth.login.mockResolvedValue(null);
  sessionStorage.clear();
  localStorage.clear();
  localStorage.setItem("bizview.locale", "es");
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

async function render(path: string) {
  await act(async () => {
    root!.render(
      <MemoryRouter initialEntries={[path]}>
        <LocaleProvider>
          <Routes>
            <Route path="/ingresar" element={<SignIn />} />
            <Route path="/" element={<p>app home</p>} />
          </Routes>
        </LocaleProvider>
      </MemoryRouter>,
    );
  });
}

async function rerender(path: string) {
  if (root) await act(async () => root?.unmount());
  container.remove();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await render(path);
}

const buttons = () => Array.from(container.querySelectorAll("button"));
const byText = (text: string) =>
  buttons().find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const form = () => container.querySelector("form");

function setValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function stubLocation() {
  const assign = vi.fn();
  const original = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: { href: original.href, origin: original.origin, assign },
  });
  return {
    assign,
    restore: () =>
      Object.defineProperty(window, "location", { configurable: true, writable: true, value: original }),
  };
}

describe("Google sign-in on the credential step", () => {
  it("renders nothing new when the installation reports google_auth: false", async () => {
    await render("/ingresar");
    expect(byText(es.google.signIn)).toBeUndefined();
    expect(byText("Continuar con Google")).toBeUndefined();
    expect(form()).not.toBeNull();
    expect(container.querySelector('input[type="email"]')).not.toBeNull();
    expect(byText(es.signIn.submit)).toBeDefined();
  });

  it("shows a real 44 px button whose name includes the provider and navigates to the start endpoint", async () => {
    branding.google_auth = true;
    const location = stubLocation();
    try {
      await render("/ingresar");
      const button = byText(es.google.signIn);
      expect(button).toBeDefined();
      expect(button!.tagName).toBe("BUTTON");
      // type=button, so it never submits the password form it sits beside.
      expect(button!.getAttribute("type")).toBe("button");
      expect(button!.textContent).toContain("Google");
      expect(button!.className).toContain("min-h-tap");
      expect(button!.disabled).toBe(false);

      await act(async () => button!.click());
      expect(location.assign).toHaveBeenCalledTimes(1);
      expect(location.assign).toHaveBeenCalledWith("/api/auth/google/start");
    } finally {
      location.restore();
    }
  });

  it("keeps the email/password form usable while the Google action is shown", async () => {
    branding.google_auth = true;
    auth.login.mockResolvedValue({ id: 1, email: "ana@example.com", must_change_password: false });
    await render("/ingresar");

    const email = container.querySelector<HTMLInputElement>('input[type="email"]')!;
    const password = container.querySelector<HTMLInputElement>('input[type="password"]')!;
    await act(async () => {
      setValue(email, "ana@example.com");
      setValue(password, "secreta-1234");
    });
    await act(async () => {
      form()!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(auth.login).toHaveBeenCalledWith("ana@example.com", "secreta-1234");
    // The session lands in the app, exactly as without Google.
    expect(container.textContent).toContain("app home");
  });

  it("is not rendered on the second-factor step", async () => {
    branding.google_auth = true;
    auth.login.mockResolvedValue("mfa");
    await render("/ingresar");
    expect(byText(es.google.signIn)).toBeDefined();

    const email = container.querySelector<HTMLInputElement>('input[type="email"]')!;
    const password = container.querySelector<HTMLInputElement>('input[type="password"]')!;
    await act(async () => {
      setValue(email, "ana@example.com");
      setValue(password, "secreta-1234");
    });
    await act(async () => {
      form()!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(container.textContent).toContain(es.mfa.stepTitle);
    expect(container.querySelector('input[autocomplete="one-time-code"]')).not.toBeNull();
    expect(byText(es.google.signIn)).toBeUndefined();
  });
});

describe("second factor required by the Google callback", () => {
  it("renders the existing code prompt from ?mfa=1, without any client-side storage", async () => {
    branding.google_auth = true;
    // The callback redirects an administrator who still owes the code to /ingresar?mfa=1.
    await render("/ingresar?mfa=1");
    expect(container.textContent).toContain(es.mfa.stepTitle);
    expect(container.querySelector('input[autocomplete="one-time-code"]')).not.toBeNull();
    expect(byText(es.google.signIn)).toBeUndefined();
    // Nothing tab-scoped is written: the URL parameter alone decides.
    expect(sessionStorage.length).toBe(0);

    await act(async () => byText(es.mfa.backToPassword)!.click());
    expect(form()).not.toBeNull();
    expect(byText(es.google.signIn)).toBeDefined();
  });

  it("writes nothing when the Google flow is started", async () => {
    branding.google_auth = true;
    const location = stubLocation();
    try {
      await render("/ingresar");
      await act(async () => byText(es.google.signIn)!.click());
      expect(location.assign).toHaveBeenCalledWith("/api/auth/google/start");
      expect(sessionStorage.length).toBe(0);
    } finally {
      location.restore();
    }
  });
});

describe("google_error codes", () => {
  const cases: [string, string][] = [
    ["disabled", es.google.errors.failed],
    ["state", es.google.errors.failed],
    ["provider", es.google.errors.failed],
    ["denied", es.google.errors.cancelled],
    ["unknown_identity", es.google.errors.notRegistered],
    ["inactive", es.google.errors.inactive],
    ["domain", es.google.errors.domain],
    ["not_a_code", es.google.errors.failed],
  ];

  it.each(cases)("?google_error=%s renders its localised message", async (code, message) => {
    await rerender(`/ingresar?google_error=${code}`);
    const alert = container.querySelector('[role="alert"]');
    expect(alert).not.toBeNull();
    expect(alert!.textContent).toContain(message);
    // The password form still works in every failure state (SC-006).
    expect(form()).not.toBeNull();
    expect(byText(es.signIn.submit)).toBeDefined();
  });
});

describe("both languages", () => {
  it("renders the Spanish action and error", async () => {
    branding.google_auth = true;
    await render("/ingresar?google_error=domain");
    expect(es.google.signIn).toBe("Continuar con Google");
    expect(byText(es.google.signIn)).toBeDefined();
    expect(container.textContent).toContain(es.google.errors.domain);
  });

  it("renders the English action and error", async () => {
    branding.google_auth = true;
    localStorage.setItem("bizview.locale", "en");
    await render("/ingresar?google_error=domain");
    expect(en.google.signIn).toBe("Continue with Google");
    expect(byText(en.google.signIn)).toBeDefined();
    expect(byText(es.google.signIn)).toBeUndefined();
    expect(container.textContent).toContain(en.google.errors.domain);
    expect(container.textContent).not.toContain(es.google.errors.domain);
  });

  it("translates every callback code in English", async () => {
    localStorage.setItem("bizview.locale", "en");
    const codes: [string, string][] = [
      ["denied", en.google.errors.cancelled],
      ["unknown_identity", en.google.errors.notRegistered],
      ["inactive", en.google.errors.inactive],
      ["domain", en.google.errors.domain],
      ["unknown", en.google.errors.failed],
    ];
    for (const [code, message] of codes) {
      await rerender(`/ingresar?google_error=${code}`);
      expect(container.textContent).toContain(message);
    }
  });
});
