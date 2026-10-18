/** Feature 023 T024: in-app links of assistant answers follow the viewer's role. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const viewer = vi.hoisted(() => ({ current: null as null | { role: string; is_superuser: boolean } }));
vi.mock("../../src/auth/AuthContext", () => ({ useOptionalUser: () => viewer.current }));

import { ChatText } from "../../src/components/assistant/ChatText";
import { resolveAppLink, splitAppLinks } from "../../src/lib/appLinks";

let root: Root | null = null;
let container: HTMLDivElement;
function render(text: string) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => root!.render(<MemoryRouter><ChatText text={text} /></MemoryRouter>));
}
afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
  root = null;
});

const SUPER = { role: "admin", is_superuser: true };
const USER = { role: "user", is_superuser: false };

describe("app links in chat answers", () => {
  it("splits app: links and keeps the rest", () => {
    expect(splitAppLinks("Ve a [Abrir Fuentes](app:/admin/fuentes) ahora.")).toEqual([
      { text: "Ve a " }, { text: "Abrir Fuentes", to: "/admin/fuentes" }, { text: " ahora." },
    ]);
  });

  it("a superuser gets a router link", () => {
    viewer.current = SUPER;
    render("Abre [Abrir Fuentes de datos](app:/admin/fuentes).");
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("/admin/fuentes");
    expect(link?.textContent).toBe("Abrir Fuentes de datos");
  });

  it("a user sees a superuser route as plain text", () => {
    viewer.current = USER;
    render("Abre [Abrir Fuentes de datos](app:/admin/fuentes).");
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toBe("Abre Abrir Fuentes de datos.");
  });

  it("an unknown route is plain text and other schemes stay literal", () => {
    viewer.current = SUPER;
    render("[x](app:/no-existe) y [web](https://example.com)");
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toBe("x y [web](https://example.com)");
    expect(resolveAppLink("/proyectos/demo", SUPER)).toBe("/proyectos/demo");
    expect(resolveAppLink("/proyectos/demo", USER)).toBeNull();
  });
});
