/** Feature 020 T082 (Constitution VIII): a new project opens with AI off, without a conversation;
 * T084/T090: cards show artifacts and problems, and an unwritable folder is said up front. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const branding = { ai_enabled: false };
vi.mock("../../src/config/BrandingContext", () => ({ useBranding: () => branding }));
vi.mock("../../src/api/projects", () => ({
  projectsApi: {
    listing: vi.fn(async () => ({ projects: [], folder_writable: true })),
    suggestSlug: vi.fn(async () => "demo"),
    create: vi.fn(async () => ({ slug: "demo" })),
    createSession: vi.fn(async () => ({ id: 7 })),
  },
  importProjectZip: vi.fn(),
}));

import { projectsApi } from "../../src/api/projects";
import { t } from "../../src/i18n/es";
import { Projects } from "../../src/pages/projects/Projects";

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.clearAllMocks();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

async function createProject() {
  await act(async () => root.render(
    <MemoryRouter initialEntries={["/proyectos"]}>
      <Routes>
        <Route path="/proyectos" element={<Projects />} />
        <Route path="/proyectos/:slug" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  ));
  const button = (label: string) =>
    Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes(label))!;
  await act(async () => button(t.projects.newProject).click());
  const input = container.querySelector("form input") as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "Demo");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => {
    container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  return container.querySelector('[data-testid="where"]')?.textContent;
}

describe("Projects page", () => {
  it("Nuevo proyecto opens the project it just created", async () => {
    expect(await createProject()).toBe("/proyectos/demo");
    expect(projectsApi.create).toHaveBeenCalledOnce();
  });

  it("cards show artifacts, applied ones and problems; an unwritable folder disables create", async () => {
    branding.ai_enabled = true;
    vi.mocked(projectsApi.listing).mockResolvedValueOnce({
      folder_writable: false,
      projects: [{
        id: 1, slug: "ventas", name: "Ventas", description: "", origin: "app", spec_seq: 2,
        status: "aplicado", spec_count: 2, conversations: 1, created_at: null, updated_at: null,
        last_activity_at: null, first_applied_at: null, withdrawn_at: null, problems: 2,
        artifacts: { integrations: ["carga"], reports: ["ventas", "margen"], distributions: [] },
        applied: { integrations: ["carga"], reports: ["ventas"], distributions: [] },
      }],
    });
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/proyectos"]}>
        <Routes><Route path="/proyectos" element={<Projects />} /></Routes>
      </MemoryRouter>,
    ));
    const text = container.textContent ?? "";
    expect(text).toContain(t.projects.folderNotWritable);
    expect(text).toContain(t.projects.artifactsSummary(1, 2, 0));
    expect(text).toContain(t.projects.appliedSummary(2));
    expect(text).toContain(t.projects.problemsCount(2));
    const create = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent?.includes(t.projects.newProject))!;
    expect(create.disabled).toBe(true);
  });
});

/** Feature 025 US3: finding a project in the list. */
const project = (id: number, slug: string, name: string, description = "") => ({
  id, slug, name, description, origin: "app" as const, spec_seq: 1, status: "borrador" as const,
  spec_count: 1, conversations: 0, created_at: null, updated_at: null, last_activity_at: null,
  first_applied_at: null, withdrawn_at: null, problems: null,
  artifacts: { integrations: [], reports: [], distributions: [] },
  applied: { integrations: [], reports: [], distributions: [] },
});

describe("Projects page search", () => {
  const list = [
    project(1, "proyecto-a", "Proyecto A", "Compras y pagos"),
    project(2, "ventas-sucursal", "Ventas por sucursal"),
    project(3, "nomina-rh", "Administración de nómina"),
  ];

  async function open() {
    vi.mocked(projectsApi.listing).mockResolvedValueOnce({ folder_writable: true, projects: list });
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/proyectos"]}>
        <Routes><Route path="/proyectos" element={<Projects />} /></Routes>
      </MemoryRouter>,
    ));
  }

  const field = () => container.querySelector('input[type="search"]') as HTMLInputElement;
  const cards = () => Array.from(container.querySelectorAll("ul > li")).map((li) => li.textContent ?? "");
  const type = async (value: string) => act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(field(), value);
    field().dispatchEvent(new Event("input", { bubbles: true }));
  });

  it("narrows the list by name, identifier or description and states how many match", async () => {
    await open();
    expect(cards()).toHaveLength(3);

    await type("proyecto-a");
    expect(cards()).toHaveLength(1);
    expect(cards()[0]).toContain("Proyecto A");
    expect(container.textContent).toContain(t.projects.matches(1));

    await type("compras");
    expect(cards()).toHaveLength(1);
    expect(cards()[0]).toContain("Proyecto A");

    await type("ventas");
    expect(cards()).toHaveLength(1);
    expect(container.textContent).toContain(t.projects.matches(1));
  });

  it("ignores case and accents", async () => {
    await open();
    await type("ADMINISTRACION");
    expect(cards()).toHaveLength(1);
    expect(cards()[0]).toContain("Administración de nómina");
  });

  it("says no project matches, without showing the first-run empty state, and clears the search", async () => {
    await open();
    await type("zzz");
    expect(cards()).toHaveLength(0);
    expect(container.textContent).toContain(t.projects.noMatch("zzz"));
    expect(container.textContent).not.toContain(t.projects.emptyText);

    const clear = container.querySelector(`button[aria-label="${t.projects.clearSearch}"]`) as HTMLButtonElement;
    await act(async () => clear.click());
    expect(field().value).toBe("");
    expect(cards()).toHaveLength(3);
  });

  it("offers no search field before there is anything to search", async () => {
    vi.mocked(projectsApi.listing).mockResolvedValueOnce({ folder_writable: true, projects: [] });
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/proyectos"]}>
        <Routes><Route path="/proyectos" element={<Projects />} /></Routes>
      </MemoryRouter>,
    ));
    expect(field()).toBeNull();
    expect(container.textContent).toContain(t.projects.emptyText);
  });
});
