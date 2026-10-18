/** Feature 023 T040: the Ayuda page for every role (list, search, topic view, links). */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn() },
  ApiError: class ApiError extends Error {},
}));
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: { role: "user", is_superuser: false } }),
  useOptionalUser: () => ({ role: "user", is_superuser: false }),
}));

import { api } from "../../src/api/client";
import { t } from "../../src/i18n/es";
import { Help } from "../../src/pages/Help";

const INDEX = {
  version: 1,
  sections: [{ id: "primeros-pasos", title: "Primeros pasos" }, { id: "tableros", title: "Tableros y reportes" }],
  topics: [
    { id: "ingreso", section: "primeros-pasos", title: "Ingresar a BizView", summary: "Cómo ingresar.", roles: ["public", "user"], related: [] },
    { id: "tableros", section: "tableros", title: "Tableros", summary: "Buscar y abrir tableros.", roles: ["user"], related: ["ingreso"] },
  ],
};
const TOPIC = {
  id: "tableros", title: "Tableros",
  body: "# Tableros\n\n## Para qué sirve\n\nVe a [Abrir Tableros](app:/tableros) o a [Abrir Fuentes](app:/admin/fuentes).\n",
  roles: ["user"], routes: ["/tableros"], related: [{ id: "ingreso", title: "Ingresar a BizView" }],
};

let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async (path: string) =>
    (path === "/api/guide" ? INDEX : TOPIC) as never);
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

async function render(url: string) {
  await act(async () => root.render(
    <MemoryRouter initialEntries={[url]}>
      <Routes><Route path="/ayuda" element={<Help />} /></Routes>
    </MemoryRouter>,
  ));
  await act(async () => new Promise((r) => setTimeout(r, 0)));
}
async function type(value: string) {
  const input = container.querySelector('input[type="search"]') as HTMLInputElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  await act(async () => {
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("Ayuda page", () => {
  it("lists the topics the API returns, grouped by section", async () => {
    await render("/ayuda");
    expect(container.textContent).toContain(t.help.title);
    expect(container.textContent).toContain("Primeros pasos");
    expect(container.textContent).toContain("Ingresar a BizView");
    expect(container.querySelector('[role="dialog"], [aria-modal]')).toBeNull();
  });

  it("search narrows the list and says when nothing matches", async () => {
    await render("/ayuda");
    await type("ingresar");
    expect(container.textContent).toContain("Ingresar a BizView");
    expect(container.textContent).not.toContain("Buscar y abrir tableros.");
    await type("zzz");
    expect(container.textContent).toContain(t.help.noMatch("zzz"));
  });

  it("?tema= shows the topic; superuser links are plain text for a user; back returns", async () => {
    await render("/ayuda?tema=tableros");
    expect(api.get).toHaveBeenCalledWith("/api/guide/topics/tableros");
    const article = container.querySelector("article");
    expect(article?.textContent).toContain("Para qué sirve");
    const links = Array.from(article!.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/tableros"]);
    expect(article?.textContent).toContain("Abrir Fuentes");
    expect(article?.textContent).toContain(t.help.related);
    expect(container.textContent).not.toContain(t.help.askAssistant);
    const back = Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes(t.help.back));
    await act(async () => back!.click());
    expect(container.querySelector("article")).toBeNull();
  });
});
