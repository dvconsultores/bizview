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
const searchField = () => container.querySelector('input[type="search"]') as HTMLInputElement;

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

  it("bounds both panes so the article scrolls, not the page (050, evidence 5 and 6)", async () => {
    await render("/ayuda?tema=tableros");
    const split = container.querySelector("section[aria-label]")!.parentElement as HTMLElement;
    // A max-height, never a fixed height: a short viewport scrolls inside the panel.
    expect(split.className).toContain("lg:max-h-[calc(100dvh-");
    expect(split.className).toContain("lg:grid-cols-");
    const list = container.querySelector("section[aria-label]") as HTMLElement;
    expect(list.className).toContain("lg:overflow-y-auto");
    expect(list.className).toContain("lg:min-h-0");
    const article = container.querySelector("article[aria-labelledby='help-topic']") as HTMLElement;
    expect(article.className).toContain("overflow-y-auto");
    expect(article.className).toContain("min-h-0");
  });

  it("on a phone a topic replaces the list and Back returns to it (050 SC-006)", async () => {
    await render("/ayuda");
    const list = container.querySelector("section[aria-label]") as HTMLElement;
    expect(list.className).not.toContain("hidden");

    await type("table");
    const first = Array.from(list.querySelectorAll("button"))
      .find((b) => b.textContent?.includes("Tableros"))!;
    await act(async () => first.click());

    const listOpen = container.querySelector("section[aria-label]") as HTMLElement;
    expect(listOpen.className).toContain("hidden");            // the article owns the screen
    expect(container.querySelector("article")).toBeTruthy();

    const back = Array.from(container.querySelectorAll("button"))
      .find((b) => b.getAttribute("aria-label") === t.help.backToList)!;
    await act(async () => back.click());
    const listBack = container.querySelector("section[aria-label]") as HTMLElement;
    expect(listBack.className).not.toContain("hidden");
    expect(searchField().value).toBe("table");                  // the search survives the trip
  });
});
