import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({ api: { get: vi.fn() }, ApiError: class ApiError extends Error {} }));
vi.mock("../../src/auth/AuthContext", () => ({ useAuth: () => ({ user: { id: 7, full_name: "Ana Pérez" } }) }));

import { api } from "../../src/api/client";
import { matches, readRecents, recordRecent } from "../../src/lib/dashboardPrefs";
import { Dashboards } from "../../src/pages/Dashboards";
import { Home } from "../../src/pages/Home";

const items = [
  { code: "ventas", name: "Ventas", description: "Resumen de ventas", icon: "chart-line", status: "available", path: "/r/ventas" },
  { code: "inv", name: "Inventario", description: "Existencias por bodega", icon: "chart-line", status: "available", path: "/r/inv" },
  { code: "cob", name: "Cobranza", description: "Cuentas por cobrar", icon: "chart-line", status: "coming_soon", path: "/d/cob" },
];

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  localStorage.clear();
  vi.mocked(api.get).mockResolvedValue({ items } as any);
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

async function render(page: "home" | "tableros" = "home") {
  await act(async () => {
    root.render(<MemoryRouter>{page === "home" ? <Home /> : <Dashboards />}</MemoryRouter>);
  });
}

async function search(text: string) {
  const input = container.querySelector<HTMLInputElement>('input[type="search"]')!;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  await act(async () => {
    setter.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("Inicio", () => {
  it("shows the greeting banner, the dashboards counter and a link to every dashboard", async () => {
    await render();
    expect(container.querySelector("h1")?.textContent).toBe("Bienvenido de nuevo, Ana");
    expect(container.querySelector("section")?.textContent).toContain("Estos son los tableros disponibles para ti.");
    expect(container.textContent).toContain("2 disponibles");
    expect(container.textContent).not.toContain("Fuentes de datos");   // admin counters: admins only
    expect(container.querySelector('a[href="/tableros"]')?.textContent).toContain("Ver todos los tableros");
    expect(container.querySelector('a[href="/r/ventas"]')).toBeNull();   // the list lives in Tableros
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it("shows favorites and recently opened dashboards that are still available", async () => {
    localStorage.setItem("bizview.home.favorites.7", JSON.stringify(["/r/ventas", "/d/cob"]));
    recordRecent(7, "/r/inv");
    recordRecent(7, "/r/borrado");
    await render();
    const fav = container.querySelector('section[aria-label="Favoritos"]')!;
    expect(fav.textContent).toContain("Ventas");
    expect(fav.textContent).not.toContain("Cobranza");          // coming soon: not openable
    const recents = container.querySelector('section[aria-label="Recientes"]')!;
    expect(recents.textContent).toContain("Inventario");
    expect(recents.textContent).not.toContain("borrado");
  });

  it("shows the empty state when the user has no dashboards and hides the tableros link", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ items: [] } as any);
    await render();
    expect(container.textContent).toContain("Aún no tienes tableros asignados");
    expect(container.textContent).toContain("0 disponibles");
    expect(container.querySelector('a[href="/tableros"]')).toBeNull();
  });
});

describe("Tableros", () => {
  it("lists every dashboard with its heading and counter (a main menu page: no Volver)", async () => {
    await render("tableros");
    expect(container.querySelector("h1")?.textContent).toBe("Tableros");
    expect(container.textContent).toContain("3 tableros");
    expect(container.textContent).toContain("Todos los tableros (3)");
    expect(container.textContent).not.toContain("Volver");
  });

  it("filters by name or description, accent-insensitive, and says when nothing matches", async () => {
    await render("tableros");
    await search("bodega");
    expect(container.textContent).toContain("Todos los tableros (1)");
    expect(container.textContent).toContain("Inventario");
    expect(container.textContent).not.toContain("Resumen de ventas");
    await search("zzz");
    expect(container.textContent).toContain("Ningún tablero coincide con «zzz».");
  });

  it("stars a dashboard as favorite (per user)", async () => {
    await render("tableros");
    const star = container.querySelector<HTMLButtonElement>('[aria-label="Añadir a favoritos: Ventas"]')!;
    await act(async () => star.click());
    expect(JSON.parse(localStorage.getItem("bizview.home.favorites.7")!)).toEqual(["/r/ventas"]);
    expect(container.querySelector('[aria-label="Quitar de favoritos: Ventas"]')?.getAttribute("aria-pressed")).toBe("true");
  });

  it("switches to the table view and remembers it", async () => {
    await render("tableros");
    const table = container.querySelector<HTMLButtonElement>('[aria-label="Vista de tabla"]')!;
    await act(async () => table.click());
    expect(table.getAttribute("aria-pressed")).toBe("true");
    expect(localStorage.getItem("bizview.home.view")).toBe("table");
    const headers = Array.from(container.querySelectorAll("thead th")).map((th) => th.textContent);
    expect(headers.slice(0, 3)).toEqual(["Tablero", "Descripción", "Estado"]);
    expect(container.querySelector('tbody a[href="/r/ventas"]')?.textContent).toBe("Ventas");
    expect(container.querySelector("tbody")?.textContent).toContain("Próximamente");
  });

  it("an older stored 'list' view opens as the table", async () => {
    localStorage.setItem("bizview.home.view", "list");
    await render("tableros");
    expect(container.querySelector("table")).not.toBeNull();
  });
});

describe("dashboard preferences", () => {
  it("search ignores case and accents", () => {
    expect(matches({ name: "Gestión", description: "" }, "GESTION")).toBe(true);
    expect(matches({ name: "A", description: "Existencias por bodega" }, "bodega")).toBe(true);
    expect(matches({ name: "A", description: "B" }, "  ")).toBe(true);
    expect(matches({ name: "A", description: "B" }, "z")).toBe(false);
  });

  it("recents keep the newest 5, without repeats", () => {
    const t0 = Date.UTC(2026, 9, 3);
    for (const [i, p] of ["/a", "/b", "/c", "/d", "/e", "/f", "/c"].entries()) {
      recordRecent(1, p, new Date(t0 + i * 1000));
    }
    expect(readRecents(1).map((r) => r.path)).toEqual(["/c", "/f", "/e", "/d", "/b"]);
  });
});
