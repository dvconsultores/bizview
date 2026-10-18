import { act, useState, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, useLocation, useNavigate } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { View } from "../../src/components/View";
import { ViewHost } from "../../src/components/ViewHost";
import { t } from "../../src/i18n/es";
import { ReauthProvider } from "../../src/components/ReauthDialog";
import { ApiError } from "../../src/api/client";

const reauthMocks = vi.hoisted(() => ({
  handler: null as null | (() => Promise<boolean>),
  post: vi.fn(),
}));

vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return {
    ...actual,
    api: { ...actual.api, post: reauthMocks.post },
    setReauthHandler: (fn: (() => Promise<boolean>) | null) => { reauthMocks.handler = fn; },
  };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function typeInto(el: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )!.set!;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

function getButton(name: string): HTMLButtonElement {
  const buttons = Array.from(
    document.querySelectorAll<HTMLButtonElement>("button"),
  );
  const button = buttons.find(
    (b) => b.textContent?.trim() === name || b.getAttribute("aria-label") === name,
  );
  if (!button) throw new Error(`Button not found: ${name}`);
  return button;
}

let navProbe: {
  navigate: ReturnType<typeof useNavigate>;
  location: ReturnType<typeof useLocation>;
} | null = null;

function NavProbe() {
  navProbe = {
    navigate: useNavigate(),
    location: useLocation(),
  };
  return null;
}

interface PageProps {
  autoFocus?: boolean;
  onClose?: () => void;
}

function Page({ autoFocus = false, onClose }: PageProps) {
  const [open, setOpen] = useState(false);

  return (
    <div data-testid="page-content">
      <label>
        Nombre
        <input aria-label="Nombre" />
      </label>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir
      </button>
      <View
        open={open}
        title="Detalle"
        autoFocus={autoFocus}
        onClose={() => {
          onClose?.();
          setOpen(false);
        }}
        footer={
          <button type="button" onClick={() => setOpen(false)}>
            Cerrar vista
          </button>
        }
      >
        <input aria-label="Campo de vista" />
      </View>
    </div>
  );
}

async function renderPage(
  ui: ReactNode,
  initialEntries: Array<string | { pathname: string; state?: unknown }> = ["/pagina"],
): Promise<void> {
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={initialEntries}>
        {ui}
        <NavProbe />
      </MemoryRouter>,
    );
  });
}

async function renderSimplePage(
  autoFocus = false,
  onClose?: () => void,
): Promise<void> {
  await renderPage(
    <ViewHost>
      <Page autoFocus={autoFocus} onClose={onClose} />
    </ViewHost>,
  );
}

function getSectionByTitle(title: string): HTMLElement {
  const headings = Array.from(document.querySelectorAll("h1"));
  const heading = headings.find((h) => h.textContent?.trim() === title);
  if (!heading) throw new Error(`View heading not found: ${title}`);
  const section = heading.closest("section");
  if (!section) throw new Error(`View section not found: ${title}`);
  return section;
}

describe("View / ViewHost", () => {
  it("hides host content while keeping it mounted and preserves its value", async () => {
    await renderSimplePage();

    const pageInput = document.querySelector<HTMLInputElement>(
      'input[aria-label="Nombre"]',
    );
    expect(pageInput).not.toBeNull();

    await act(async () => {
      typeInto(pageInput!, "Ana");
    });
    expect(pageInput!.value).toBe("Ana");

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    const pageContent = document.querySelector<HTMLDivElement>(
      '[data-testid="page-content"]',
    );
    expect(pageContent).not.toBeNull();
    expect(pageContent!.parentElement).not.toBeNull();
    expect(pageContent!.parentElement!.hasAttribute("hidden")).toBe(true);
    expect(
      document.querySelector<HTMLInputElement>('input[aria-label="Nombre"]'),
    ).not.toBeNull();

    await act(async () => {
      getButton("Cerrar vista").click();
    });
    await flush();

    const pageContentAfter = document.querySelector<HTMLDivElement>(
      '[data-testid="page-content"]',
    );
    expect(pageContentAfter).not.toBeNull();
    expect(pageContentAfter!.parentElement).not.toBeNull();
    expect(pageContentAfter!.parentElement!.hasAttribute("hidden")).toBe(false);
    expect(
      document.querySelector<HTMLInputElement>('input[aria-label="Nombre"]')
        ?.value,
    ).toBe("Ana");
  });

  it("renders the view inside the innermost host", async () => {
    await renderPage(
      <ViewHost>
        <div data-testid="outer-host-content">
          <ViewHost>
            <Page />
          </ViewHost>
        </div>
      </ViewHost>,
    );

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    const section = getSectionByTitle("Detalle");
    const outerContent = document.querySelector<HTMLDivElement>(
      '[data-testid="outer-host-content"]',
    );
    expect(outerContent).not.toBeNull();

    const innerContentWrapper = outerContent!
      .firstElementChild as HTMLDivElement | null;
    expect(innerContentWrapper).not.toBeNull();
    expect(innerContentWrapper!.hasAttribute("hidden")).toBe(true);

    const outerContentWrapper = outerContent!
      .parentElement as HTMLDivElement | null;
    expect(outerContentWrapper).not.toBeNull();
    expect(outerContentWrapper!.hasAttribute("hidden")).toBe(false);

    expect(innerContentWrapper!.contains(section)).toBe(false);
    expect(outerContent!.contains(section)).toBe(true);
  });

  it("stacks views and reveals the previous one when the top closes", async () => {
    function TwoViews() {
      const [firstOpen, setFirstOpen] = useState(false);
      const [secondOpen, setSecondOpen] = useState(false);

      return (
        <>
          <button type="button" onClick={() => setFirstOpen(true)}>
            Abrir primera
          </button>
          <button type="button" onClick={() => setSecondOpen(true)}>
            Abrir segunda
          </button>
          <View
            open={firstOpen}
            title="Primera"
            onClose={() => setFirstOpen(false)}
          >
            Vistas de la primera
          </View>
          <View
            open={secondOpen}
            title="Segunda"
            onClose={() => setSecondOpen(false)}
            footer={
              <button type="button" onClick={() => setSecondOpen(false)}>
                Cerrar segunda
              </button>
            }
          >
            Vistas de la segunda
          </View>
        </>
      );
    }

    await renderPage(
      <ViewHost>
        <TwoViews />
      </ViewHost>,
    );

    await act(async () => {
      getButton("Abrir primera").click();
    });
    await flush();

    await act(async () => {
      getButton("Abrir segunda").click();
    });
    await flush();

    const sectionA = getSectionByTitle("Primera");
    const sectionB = getSectionByTitle("Segunda");
    expect(sectionA.hasAttribute("hidden")).toBe(true);
    expect(sectionB.hasAttribute("hidden")).toBe(false);

    await act(async () => {
      getButton("Cerrar segunda").click();
    });
    await flush();

    const sectionAAfter = getSectionByTitle("Primera");
    expect(sectionAAfter.hasAttribute("hidden")).toBe(false);
    expect(document.querySelector("h1")?.textContent?.trim()).not.toBe(
      "Segunda",
    );
  });

  it("closes via browser back navigation", async () => {
    const onClose = vi.fn();
    await renderSimplePage(false, onClose);

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    expect(getSectionByTitle("Detalle")).toBeTruthy();

    await act(async () => {
      navProbe!.navigate(-1);
    });
    await flush();

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector("h1")).toBeNull();
  });

  it("UI close pops the view history entry without calling onClose from history", async () => {
    const onClose = vi.fn();
    await renderSimplePage(false, onClose);

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    const stateAfterOpen = navProbe!.location.state as
      | { view?: unknown }
      | null;
    const viewIds = Array.isArray(stateAfterOpen?.view)
      ? (stateAfterOpen.view as unknown[])
      : [];
    expect(viewIds).toHaveLength(1);

    await act(async () => {
      getButton("Cerrar vista").click();
    });
    await flush();

    const stateAfterClose = navProbe!.location.state as
      | { view?: unknown }
      | null;
    const viewIdsAfterClose = Array.isArray(stateAfterClose?.view)
      ? (stateAfterClose.view as unknown[])
      : [];
    expect(viewIdsAfterClose).toHaveLength(0);
    expect(navProbe!.location.pathname).toBe("/pagina");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes with Escape", async () => {
    const onClose = vi.fn();
    await renderSimplePage(false, onClose);

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    expect(getSectionByTitle("Detalle")).toBeTruthy();

    await act(async () => {
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    });
    await flush();

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector("h1")).toBeNull();
  });

  it("focuses the heading on open and restores focus on close", async () => {
    await renderSimplePage(false);

    await act(async () => {
      const openButton = getButton("Abrir");
      openButton.focus();
      openButton.click();
    });
    await flush();

    const heading = getSectionByTitle("Detalle").querySelector("h1");
    expect(heading).not.toBeNull();
    expect(document.activeElement).toBe(heading);
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);

    await act(async () => {
      getButton("Cerrar vista").click();
    });
    await flush();

    expect(document.activeElement).toBe(getButton("Abrir"));
  });

  it("focuses the first field with autoFocus and restores focus on close", async () => {
    await renderSimplePage(true);

    await act(async () => {
      const openButton = getButton("Abrir");
      openButton.focus();
      openButton.click();
    });
    await flush();

    const viewInput = document.querySelector<HTMLInputElement>(
      'input[aria-label="Campo de vista"]',
    );
    expect(viewInput).not.toBeNull();
    expect(document.activeElement).toBe(viewInput);
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0);

    await act(async () => {
      getButton("Cerrar vista").click();
    });
    await flush();

    expect(document.activeElement).toBe(getButton("Abrir"));
  });

  it("back button has the expected label and calls onClose", async () => {
    const onClose = vi.fn();
    await renderSimplePage(false, onClose);

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    const backButton = getButton(t.common.back);
    expect(backButton).toBeTruthy();

    await act(async () => {
      backButton.click();
    });
    await flush();

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector("h1")).toBeNull();
  });

  it("does not use dialog semantics and has an accessible heading", async () => {
    await renderSimplePage();

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector("[aria-modal]")).toBeNull();

    const heading = getSectionByTitle("Detalle").querySelector("h1");
    const section = getSectionByTitle("Detalle");
    expect(section.getAttribute("aria-labelledby")).toBe(heading?.id);
  });

  it("closes on back after open -> back -> forward -> reopen", async () => {
    const onClose = vi.fn();
    await renderSimplePage(false, onClose);

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();

    await act(async () => {
      navProbe!.navigate(-1);
    });
    await flush();
    expect(document.querySelector("h1")).toBeNull();
    expect(onClose).toHaveBeenCalledTimes(1);

    await act(async () => {
      navProbe!.navigate(1);
    });
    await flush();
    expect(document.querySelector("h1")).toBeNull();

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();
    expect(document.querySelector("h1")).not.toBeNull();
    const state = navProbe!.location.state as { view?: unknown } | null;
    expect(Array.isArray(state?.view)).toBe(true);
    expect((state!.view as unknown[]).length).toBe(1);

    await act(async () => {
      navProbe!.navigate(-1);
    });
    await flush();
    expect(document.querySelector("h1")).toBeNull();
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("restores the page scroll position after the view closes", async () => {
    const setScrollY = (v: number) =>
      Object.defineProperty(window, "scrollY", {
        configurable: true,
        writable: true,
        value: v,
      });

    setScrollY(640);

    try {
      await renderSimplePage();

      await act(async () => {
        getButton("Abrir").click();
      });
      await flush();

      expect(vi.mocked(window.scrollTo)).toHaveBeenCalledWith(0, 0);
      expect(getSectionByTitle("Detalle")).toBeTruthy();

      setScrollY(0);
      vi.mocked(window.scrollTo).mockClear();

      await act(async () => {
        getButton("Cerrar vista").click();
      });
      await flush();

      expect(window.scrollTo).toHaveBeenLastCalledWith(0, 640);
    } finally {
      setScrollY(0);
    }
  });

  it("ignores a stale view id from a reloaded entry and closes on back", async () => {
    const onClose = vi.fn();
    await renderPage(
      <ViewHost>
        <Page onClose={onClose} />
      </ViewHost>,
      ["/inicio", { pathname: "/pagina", state: { view: ["_r_1_"] } }],
    );
    await flush();
    expect(document.querySelector("h1")).toBeNull();

    await act(async () => {
      getButton("Abrir").click();
    });
    await flush();
    expect(document.querySelector("h1")).not.toBeNull();
    const state = navProbe!.location.state as { view?: unknown } | null;
    expect(Array.isArray(state?.view)).toBe(true);
    const view = (state!.view as unknown[]).map(String);
    expect(view.length).toBe(1);
    expect(view).not.toContain("_r_1_");

    await act(async () => {
      navProbe!.navigate(-1);
    });
    await flush();
    expect(document.querySelector("h1")).toBeNull();
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(navProbe!.location.pathname).toBe("/pagina");
  });
});

describe("ReauthProvider", () => {
  beforeEach(() => {
    reauthMocks.post.mockReset();
    reauthMocks.handler = null;
  });

  function Page() {
    return (
      <div>
        <input aria-label="Nombre" />
      </div>
    );
  }

  async function renderReauth() {
    await renderPage(
      <ReauthProvider>
        <ViewHost>
          <Page />
        </ViewHost>
      </ReauthProvider>,
    );
    await flush();
  }

  function passwordSection(): HTMLElement {
    return getSectionByTitle(t.reauth.title);
  }

  function passwordInput(): HTMLInputElement {
    const section = passwordSection();
    const input = section.querySelector('input[type="password"]');
    if (!input) throw new Error("password input not found");
    return input as HTMLInputElement;
  }

  async function ask() {
    if (!reauthMocks.handler) throw new Error("reauth handler not set");
    const p = reauthMocks.handler();
    await flush();
    return { p };
  }

  it("shares one pending promise across concurrent ask() calls", async () => {
    await renderReauth();
    if (!reauthMocks.handler) throw new Error("reauth handler not set");
    let p1: Promise<boolean>;
    let p2: Promise<boolean>;
    act(() => {
      p1 = reauthMocks.handler!();
      p2 = reauthMocks.handler!();
    });
    await flush();
    expect(p1).toBe(p2);
    expect(document.querySelectorAll("h1").length).toBe(1);
    const input = passwordInput();
    typeInto(input, "secreto-1");
    reauthMocks.post.mockResolvedValue({});
    const results = await act(async () => {
      getButton(t.reauth.confirm).click();
      return Promise.all([p1, p2]);
    });
    await flush();
    expect(results).toEqual([true, true]);
    expect(reauthMocks.post).toHaveBeenCalledTimes(1);
    expect(reauthMocks.post).toHaveBeenCalledWith("/api/auth/reauth", { password: "secreto-1" });
    expect(document.body.textContent).not.toContain(t.reauth.title);
  });

  it("resolves false when the user cancels", async () => {
    await renderReauth();
    const { p } = await ask();
    let resolved = false;
    let value: boolean | null = null;
    void p.then((v) => { resolved = true; value = v; });
    await act(async () => {
      getButton(t.common.cancel).click();
      await Promise.resolve();
    });
    await flush();
    expect(resolved).toBe(true);
    expect(value).toBe(false);
    expect(reauthMocks.post).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain(t.reauth.title);
  });

  it("keeps the view open on wrong password and resolves true on retry", async () => {
    await renderReauth();
    const { p } = await ask();
    let settled = false;
    void p.then(() => { settled = true; });
    typeInto(passwordInput(), "mala");
    reauthMocks.post.mockRejectedValueOnce(new ApiError(401, "invalid_credentials", "Contraseña incorrecta."));
    await act(async () => {
      getButton(t.reauth.confirm).click();
      await flush();
    });
    await flush();
    expect(settled).toBe(false);
    expect(passwordSection().textContent).toContain("Contraseña incorrecta.");
    expect(passwordInput().value).toBe("");
    reauthMocks.post.mockResolvedValueOnce({});
    typeInto(passwordInput(), "buena");
    const result = await act(async () => {
      getButton(t.reauth.confirm).click();
      return p;
    });
    await flush();
    expect(result).toBe(true);
    expect(reauthMocks.post).toHaveBeenLastCalledWith("/api/auth/reauth", { password: "buena" });
    expect(document.body.textContent).not.toContain(t.reauth.title);
  });

  it("resolves false and closes on 429", async () => {
    await renderReauth();
    const { p } = await ask();
    typeInto(passwordInput(), "x".repeat(8));
    reauthMocks.post.mockRejectedValueOnce(new ApiError(429, "rate_limited", "Demasiados intentos."));
    const result = await act(async () => {
      getButton(t.reauth.confirm).click();
      return p;
    });
    await flush();
    expect(result).toBe(false);
    expect(document.body.textContent).not.toContain(t.reauth.title);
  });

  it("preserves the page behind while the view is open", async () => {
    await renderReauth();
    const pageInput = container.querySelector('input[aria-label="Nombre"]') as HTMLInputElement;
    typeInto(pageInput, "Ana");
    const { p } = await ask();
    expect(pageInput.closest("[hidden]")).not.toBe(null);
    await act(async () => {
      getButton(t.common.cancel).click();
      await p;
    });
    await flush();
    expect(pageInput.closest("[hidden]")).toBe(null);
    expect(pageInput.value).toBe("Ana");

    const { p: p2 } = await ask();
    typeInto(passwordInput(), "valida");
    reauthMocks.post.mockResolvedValueOnce({});
    await act(async () => {
      getButton(t.reauth.confirm).click();
      await p2;
    });
    await flush();
    expect(pageInput.closest("[hidden]")).toBe(null);
    expect(pageInput.value).toBe("Ana");
  });
});
