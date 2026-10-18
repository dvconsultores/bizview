import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type MockUser = { id: number; locale?: "es" | "en" | null };
let currentUser: MockUser | null = null;
const setUser = vi.fn((u: MockUser | null) => { currentUser = u; });
const toast = vi.fn();
const api = { patch: vi.fn() };

vi.doMock("../../src/auth/AuthContext", () => ({ useAuth: () => ({ user: currentUser, setUser }) }));
vi.doMock("../../src/components/Toast", () => ({ useToast: () => toast }));
vi.doMock("../../src/api/client", () => ({ api }));
vi.doMock("../../src/config/BrandingContext", () => ({ useBranding: () => ({ default_locale: undefined }) }));

let root: Root | null = null;
let host: HTMLDivElement | null = null;

describe("LanguageSwitcher", () => {
  const render = async (props: { inMenu?: boolean; compact?: boolean } = {}) => {
    const { LocaleProvider } = await import("../../src/i18n");
    const { LanguageSwitcher } = await import("../../src/components/LanguageSwitcher");
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(
        <LocaleProvider>
          <LanguageSwitcher {...props} />
        </LocaleProvider>
      );
    });
    return host!;
  };

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();
    setUser.mockImplementation((u: MockUser | null) => { currentUser = u; });
    api.patch.mockReset();
    localStorage.clear();
    document.documentElement.lang = "es";
    Object.defineProperty(navigator, "languages", { value: ["fr-FR"], configurable: true });
    currentUser = null;
  });

  afterEach(async () => {
    if (root) {
      await act(async () => {
        root!.unmount();
      });
      root = null;
    }
    host?.remove();
    host = null;
  });

  it("full variant shows three options and follows device cache", async () => {
    const host = await render();
    const radios = host.querySelectorAll('[role="radio"]');
    expect(radios).toHaveLength(3);
    expect(radios[0].textContent).toBe("Español");
    expect(radios[1].textContent).toBe("English");
    expect(radios[2].textContent).toBe("Idioma del navegador");
    expect(host.querySelector('[role="radiogroup"]')?.getAttribute("aria-label")).toBe("Idioma");
    expect(radios[2].getAttribute("aria-checked")).toBe("true");
    expect(radios[0].getAttribute("lang")).toBe("es");
    expect(radios[1].getAttribute("lang")).toBe("en");
    expect(radios[2].hasAttribute("lang")).toBe(false);
  });

  it("clicking English stores device choice and updates document language", async () => {
    const host = await render();
    const radios = host.querySelectorAll('[role="radio"]');
    await act(async () => { (radios[1] as HTMLButtonElement).click(); });
    expect(document.documentElement.lang).toBe("en");
    expect(localStorage.getItem("bizview.locale")).toBe("en");
    expect(host.querySelector('[role="radiogroup"]')?.getAttribute("aria-label")).toBe("Language");
    const updated = host.querySelectorAll('[role="radio"]');
    expect(updated[2].textContent).toBe("Browser language");
    expect(updated[1].getAttribute("aria-checked")).toBe("true");
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("signed-in user persists the choice via api", async () => {
    currentUser = { id: 1, locale: "es" };
    api.patch.mockResolvedValue({ theme: "system", locale: "en" });
    const host = await render();
    const radios = host.querySelectorAll('[role="radio"]');
    expect(radios[0].getAttribute("aria-checked")).toBe("true");
    await act(async () => { (radios[1] as HTMLButtonElement).click(); });
    expect(api.patch).toHaveBeenCalledWith("/api/me/preferences", { locale: "en" });
  });

  it("compact variant shows two options and uses resolved language", async () => {
    Object.defineProperty(navigator, "languages", { value: ["en-US"], configurable: true });
    const host = await render({ compact: true });
    const radios = host.querySelectorAll('[role="radio"]');
    expect(radios).toHaveLength(2);
    expect(radios[0].textContent).toBe("Español");
    expect(radios[1].textContent).toBe("English");
    expect(radios[1].getAttribute("aria-checked")).toBe("true");
  });

  it("keyboard arrows move and select", async () => {
    localStorage.setItem("bizview.locale", "es");
    const host = await render();
    const radios = host.querySelectorAll('[role="radio"]');
    expect(radios[0].getAttribute("aria-checked")).toBe("true");
    (radios[0] as HTMLButtonElement).focus();
    await act(async () => {
      radios[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    const updated = host.querySelectorAll('[role="radio"]');
    expect(updated[1].getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(updated[1]);
    expect(updated[0].getAttribute("tabindex")).toBe("-1");
    expect(updated[1].getAttribute("tabindex")).toBe("0");
  });

  it("inMenu uses menuitemradio and short browser label", async () => {
    const host = await render({ inMenu: true });
    const items = host.querySelectorAll('[role="menuitemradio"]');
    expect(items).toHaveLength(3);
    expect(host.querySelector('[role="group"]')).toBeTruthy();
    expect(items[2].textContent).toBe("Navegador");
  });
});
