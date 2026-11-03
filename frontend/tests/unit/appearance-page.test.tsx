/** Feature 047 (US3): Administración → Apariencia is the theme library — every theme with a light
 * and a dark preview, the upload with each problem it returned, and the four actions. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
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
      public retryAfter?: number,
      public details: Record<string, unknown> = {},
    ) {
      super(message);
    }
  },
}));

vi.mock("../../src/components/Toast", () => ({ useToast: () => vi.fn() }));

import { api, ApiError } from "../../src/api/client";
import { Appearance } from "../../src/pages/admin/Appearance";
import { ViewHost } from "../../src/components/ViewHost";
import { t } from "../../src/i18n/es";
import { BUILTIN_THEMES, type Theme } from "../../src/theme/themes";
import type { ThemeLibrary } from "../../src/api/types";

let container: HTMLDivElement;
let root: Root | null = null;

const UPLOADED: Theme = {
  ...BUILTIN_THEMES.impacto,
  id: "acme-azul",
  name: "Acme · azul",
  name_en: "Acme · blue",
};

const LIBRARY: ThemeLibrary = {
  themes: [
    { id: "impacto", name: "Impacto", name_en: "Impact", version: 1, origin: "builtin",
      project: null, tokens: BUILTIN_THEMES.impacto },
    { id: "clasico", name: "Clásico", name_en: "Classic", version: 1, origin: "builtin",
      project: null, tokens: BUILTIN_THEMES.clasico },
    { id: "acme-azul", name: "Acme · azul", name_en: "Acme · blue", version: 2, origin: "upload",
      project: null, tokens: UPLOADED },
    { id: "acme-verde", name: "Acme · verde", name_en: "Acme · green", version: 1,
      origin: "project", project: 7, tokens: { ...UPLOADED, id: "acme-verde" } },
  ],
  installation: "impacto",
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue(LIBRARY);
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.innerHTML = "";
});

async function render() {
  await act(async () => {
    root?.render(
      <MemoryRouter initialEntries={["/admin/apariencia"]}>
        <ViewHost>
          <Appearance />
        </ViewHost>
      </MemoryRouter>,
    );
  });
  await act(async () => {
    await Promise.resolve();
  });
}

const button = (text: string) =>
  Array.from(document.querySelectorAll("button")).find((el) => el.textContent === text) as
    | HTMLButtonElement
    | undefined;

describe("Appearance library", () => {
  it("lists every theme with a light and a dark preview and its origin", async () => {
    await render();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/admin/themes");
    expect(document.querySelectorAll("[data-theme-preview]")).toHaveLength(
      LIBRARY.themes.length * 2,
    );
    const text = document.body.textContent ?? "";
    expect(text).toContain(t.appearance.originBuiltin);
    expect(text).toContain(t.appearance.originUpload);
    expect(text).toContain(t.appearance.originProject);
    expect(text).toContain("acme-verde");
    expect(text).toContain(t.appearance.version.replace("{version}", "2"));
  });

  it("fills the page container with a responsive grid (050, evidence 1 and 2)", async () => {
    await render();
    // The defect: the library sat in a 56 rem column with a fixed two-column grid, so a wide screen
    // had an unexplained empty half and the previews were the tallest thing on it.
    const grid = container.querySelector("[data-theme-grid]") as HTMLElement;
    expect(grid.className).toContain("grid-cols-1");
    expect(grid.className).toContain("sm:grid-cols-2");
    expect(grid.className).toContain("xl:grid-cols-3");
    // No page-level narrow width anywhere in the rendered tree.
    expect(container.innerHTML).not.toMatch(/max-w-(?:2xl|3xl|4xl|5xl)/);
    // Cards fill their cell so a row has one height.
    const card = grid.firstElementChild as HTMLElement;
    expect(card.className).toContain("h-full");
    expect(card.className).toContain("flex-col");
  });

  it("marks the selected theme with a word, not only a colour (050 SC-003)", async () => {
    await render();
    const current = Array.from(container.querySelectorAll("span"))
      .find((el) => el.textContent?.trim() === t.appearance.current);
    expect(current).toBeTruthy();
    expect(current!.className).toContain("bg-accent-soft");
  });

  it("draws the preview with the theme's own colours", async () => {
    await render();
    const preview = document.querySelector('[data-theme-preview="light"]') as HTMLElement;
    const style = preview.getAttribute("style") ?? "";
    const [r, g, b] = [1, 3, 5].map((i) =>
      parseInt(BUILTIN_THEMES.impacto.light.surface.slice(i, i + 2), 16),
    );
    expect(style).toContain(`${r} ${g} ${b}`);
  });

  it("marks the installation theme in use and offers no apply for it", async () => {
    await render();
    expect(document.body.textContent).toContain(t.appearance.current);
    // Feature 051: the installed card's action says it is in use instead of offering the same
    // change again — so there is one apply fewer than there are themes.
    const applies = Array.from(document.querySelectorAll("button")).filter(
      (el) => el.textContent === t.appearance.apply,
    );
    expect(applies).toHaveLength(LIBRARY.themes.length - 1);
    const installed = container.querySelector('[data-installed="true"]') as HTMLElement;
    expect(installed).toBeTruthy();
    const action = Array.from(installed.querySelectorAll("button")).find(
      (el) => el.textContent === t.appearance.inUse,
    ) as HTMLButtonElement;
    expect(action.disabled).toBe(true);
    expect(applies.every((el) => !(el as HTMLButtonElement).disabled)).toBe(true);
  });

  it("applies a theme through the settings endpoint, and nothing before the server agrees", async () => {
    vi.mocked(api.put).mockResolvedValue({ theme_id: "acme-azul" });
    await render();
    const card = container.querySelector('[data-theme-card="acme-azul"]') as HTMLElement;
    const apply = Array.from(card.querySelectorAll("button")).find(
      (el) => el.textContent === t.appearance.apply,
    ) as HTMLButtonElement;
    await act(async () => apply.click());
    expect(vi.mocked(api.put)).toHaveBeenCalledWith("/api/admin/settings/theme", {
      theme_id: "acme-azul",
    });
    // Feature 051: no reload — the shared config is re-read so the whole application repaints.
    expect(vi.mocked(api.get)).toHaveBeenCalledWith("/api/admin/themes");
  });

  it("keeps the previous theme when the server refuses the change (FR-005)", async () => {
    vi.mocked(api.put).mockRejectedValue(new ApiError(403, "forbidden", "No puedes cambiarlo."));
    await render();
    const card = container.querySelector('[data-theme-card="acme-azul"]') as HTMLElement;
    const apply = Array.from(card.querySelectorAll("button")).find(
      (el) => el.textContent === t.appearance.apply,
    ) as HTMLButtonElement;
    await act(async () => apply.click());
    expect(document.body.textContent).toContain("No puedes cambiarlo.");
    expect(container.querySelector('[data-installed="true"]')).toBeTruthy();
  });

  it("refuses to delete a theme the product ships and offers the delete for the others", async () => {
    await render();
    const labels = Array.from(document.querySelectorAll("button")).map(
      (el) => el.getAttribute("aria-label") ?? "",
    );
    expect(labels.some((label) => label === `${t.appearance.delete} Impacto`)).toBe(false);
    expect(labels).toContain(`${t.appearance.delete} Acme · azul`);
    expect(labels).toContain(`${t.appearance.download} Acme · verde`);
    expect(labels).toContain(`${t.appearance.duplicate} Acme · verde`);
  });

  it("names the reports that keep a theme alive when the delete is refused", async () => {
    vi.mocked(api.del).mockRejectedValue(
      new ApiError(409, "theme_in_use", "en uso", {}, undefined, { reports: ["ventas", "stock"] }),
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await render();
    const del = document.querySelector(
      `[aria-label="${t.appearance.delete} Acme · azul"]`,
    ) as HTMLButtonElement;
    await act(async () => del.click());
    expect(vi.mocked(api.del)).toHaveBeenCalledWith("/api/admin/themes/acme-azul");
    expect(document.body.textContent).toContain("ventas, stock");
  });

  it("shows every problem an invalid upload returned, with its path", async () => {
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(422, "theme_invalid", "tema inválido", {}, undefined, {
        problems: [
          { path: "light.text", code: "contrast", message: "light.text vs light.surface: 1.16:1" },
          { path: "dark.series", code: "series_length", message: "two series" },
        ],
      }),
    );
    await render();
    await act(async () => button(t.appearance.upload)?.click());
    const area = document.querySelector("#theme-yaml") as HTMLTextAreaElement;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setter?.call(area, "id: acme-azul");
      area.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const submit = Array.from(document.querySelectorAll("button")).filter(
      (el) => el.textContent === t.appearance.upload,
    );
    await act(async () => submit[submit.length - 1].click());
    expect(vi.mocked(api.post)).toHaveBeenCalledWith("/api/admin/themes", {
      yaml: "id: acme-azul",
    });
    const text = document.body.textContent ?? "";
    expect(text).toContain("light.text: light.text vs light.surface: 1.16:1");
    expect(text).toContain("dark.series: two series");
    expect(document.querySelectorAll("[data-theme-problem]")).toHaveLength(2);
  });

  it("asks before replacing a theme that already exists, then replaces it", async () => {
    vi.mocked(api.post)
      .mockRejectedValueOnce(
        new ApiError(409, "theme_exists", "existe", {}, undefined, { id: "acme-azul", version: 2 }),
      )
      .mockResolvedValueOnce({ theme: { id: "acme-azul" } });
    await render();
    await act(async () => button(t.appearance.upload)?.click());
    const area = document.querySelector("#theme-yaml") as HTMLTextAreaElement;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setter?.call(area, "id: acme-azul");
      area.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const submits = () =>
      Array.from(document.querySelectorAll("button")).filter(
        (el) => el.textContent === t.appearance.upload,
      );
    await act(async () => submits()[submits().length - 1].click());
    expect(document.body.textContent).toContain(
      t.appearance.replaceQuestion.replace("{id}", "acme-azul").replace("{version}", "2"),
    );
    await act(async () => button(t.appearance.replace)?.click());
    expect(vi.mocked(api.post)).toHaveBeenLastCalledWith("/api/admin/themes?replace=true", {
      yaml: "id: acme-azul",
    });
  });

  it("starts the upload from an existing theme so it can be edited and re-uploaded", async () => {
    await render();
    const copy = document.querySelector(
      `[aria-label="${t.appearance.duplicate} Acme · azul"]`,
    ) as HTMLButtonElement;
    await act(async () => copy.click());
    const area = document.querySelector("#theme-yaml") as HTMLTextAreaElement;
    expect(area.value).toContain("acme-azul");
  });

  it("shows the server message when the library cannot be read", async () => {
    vi.mocked(api.get).mockRejectedValue(new ApiError(500, "internal", "Sin conexión"));
    await render();
    expect(document.body.textContent).toContain("Sin conexión");
  });
});
