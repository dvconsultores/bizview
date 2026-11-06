/** Feature 020 T082/T084/T090: cards show artifacts and problems, and an unwritable folder is said
 * up front. Feature 049: the page is import-only — no create affordance in any state — and the two
 * import allowances are shown before the zip is uploaded. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const branding = { ai_enabled: false };
vi.mock("../../src/config/BrandingContext", () => ({ useBranding: () => branding }));
const LIMITS = {
  artifacts: { name: "artifacts", max_files: 400, max_kb: 2048, max_mb: 20, label: "specs/" },
  assets: { name: "assets", max_files: 2000, max_kb: 300, max_mb: 25, label: "assets/" },
  zip_max_mb: 45,
  stored: { artifact_max_files: null, artifact_max_kb: null, artifact_max_mb: null,
            asset_max_files: null, asset_max_kb: null, asset_max_mb: null },
};

vi.mock("../../src/api/projects", () => ({
  projectsApi: {
    listing: vi.fn(async () => ({ projects: [], folder_writable: true })),
    limits: vi.fn(async () => LIMITS),
    saveLimits: vi.fn(async () => LIMITS),
  },
  importProjectZip: vi.fn(),
}));

const index = vi.fn(async () => [
  { name: "ventas/project.yaml", size: 120 },
  { name: "ventas/assets/coins/BTC.png", size: 3800 },
]);
vi.mock("../../src/lib/zipIndex", () => ({ readZipIndex: (...args: unknown[]) => index(...args) }));

import { importProjectZip, projectsApi } from "../../src/api/projects";
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

async function open() {
  await act(async () => root.render(
    <MemoryRouter initialEntries={["/proyectos"]}>
      <Routes>
        <Route path="/proyectos" element={<Projects />} />
        <Route path="/proyectos/:slug" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  ));
}

const buttons = () => Array.from(container.querySelectorAll("button"));
const button = (label: string) => buttons().find((b) => b.textContent?.includes(label));

/** Choose a zip: the page reads its index and shows what it carries before anything is sent. */
async function chooseZip() {
  const input = container.querySelector("#project-zip") as HTMLInputElement;
  const file = new File([new Uint8Array([1, 2, 3])], "ventas.zip", { type: "application/zip" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => { input.dispatchEvent(new Event("change", { bubbles: true })); });
  await act(async () => { await Promise.resolve(); });
  return file;
}

describe("Projects page", () => {
  it("previews the diff and then imports the zip (055)", async () => {
    const diff = {
      added: ["reports/cripto/report.yaml"], changed: [], removed: [],
      specs: { added: [], removed: [] }, ids: { added: [], removed: [] },
      counts: { added: 1, changed: 0, removed: 0, specs_added: 0, specs_removed: 0,
                ids_added: 0, ids_removed: 0 },
      truncated: false, base_revision: 1,
    };
    vi.mocked(importProjectZip)
      .mockResolvedValueOnce({ project: { slug: "ventas" } as never, ignored: [],
                               validation: { errors: [] } as never, mode: "reimported",
                               revision: null, diff: diff as never })
      .mockResolvedValueOnce({ project: { slug: "ventas", name: "Ventas" } as never, ignored: [],
                               validation: { errors: [] } as never, mode: "reimported",
                               revision: { number: 2 } as never, diff: diff as never });
    await open();
    await chooseZip();

    // First press asks the server what would change; nothing is written.
    await act(async () => { button(t.projects.importNow)!.click(); });
    await act(async () => { await Promise.resolve(); });
    expect(importProjectZip).toHaveBeenCalledTimes(1);
    expect(vi.mocked(importProjectZip).mock.calls[0][1]).toEqual({ copy: false, dryRun: true });
    expect(container.querySelector('[data-testid="revision-diff"]')).not.toBeNull();
    expect(container.textContent).toContain(t.projects.diff.reimportTitle(1, 0, 0, 1));

    // Second press writes it.
    await act(async () => { button(t.projects.importNow)!.click(); });
    await act(async () => { await Promise.resolve(); });
    expect(importProjectZip).toHaveBeenCalledTimes(2);
    expect(vi.mocked(importProjectZip).mock.calls[1][1]).toEqual({ copy: false,
                                                                 replaceDraft: false });
    expect(container.textContent).toContain(t.projects.reimportedTitle("Ventas", 2));
    expect(projectsApi).not.toHaveProperty("create");
  });

  it("asks before replacing a draft with editor changes (055)", async () => {
    const diff = {
      added: [], changed: ["reports/cripto/report.yaml"], removed: [],
      specs: { added: [], removed: [] }, ids: { added: [], removed: [] },
      counts: { added: 0, changed: 1, removed: 0, specs_added: 0, specs_removed: 0,
                ids_added: 0, ids_removed: 0 },
      truncated: false, base_revision: 2,
    };
    vi.mocked(importProjectZip).mockResolvedValueOnce({
      project: { slug: "ventas" } as never, ignored: [], validation: { errors: [] } as never,
      mode: "reimported", revision: null, diff: diff as never, needs_confirmation: true,
    });
    await open();
    await chooseZip();
    await act(async () => { button(t.projects.importNow)!.click(); });
    await act(async () => { await Promise.resolve(); });
    expect(container.textContent).toContain(t.projects.replaceDraftTitle);
    expect(button(t.projects.replaceDraft)).toBeDefined();
  });

  it("offers no create affordance in either state (049)", async () => {
    await open();
    const labels = buttons().map((b) => b.textContent ?? "");
    expect(labels.some((label) => label.includes(t.projects.importProject))).toBe(true);
    expect(container.textContent).not.toContain("Nuevo proyecto");
    expect(container.querySelector("form")).toBeNull();
  });

  it("shows what the zip carries before uploading it", async () => {
    await open();
    await chooseZip();
    const text = container.textContent ?? "";
    expect(text).toContain(t.projects.preflight.title);
    expect(text).toContain(t.projects.preflight.artifacts);
    expect(text).toContain(t.projects.preflight.assets);
    expect(text).toContain("1/400");            // one artifact, of four hundred allowed
    expect(text).toContain("1/2000");           // one image
    expect(button(t.projects.importNow)!.disabled).toBe(false);
  });

  it("refuses an over-limit zip before it is uploaded, naming the allowance", async () => {
    index.mockResolvedValueOnce(Array.from({ length: 2001 }, (_, i) => ({
      name: `ventas/assets/coins/${i}.png`, size: 1000,
    })));
    await open();
    await chooseZip();
    const text = container.textContent ?? "";
    expect(text).toContain(t.projects.preflight.assets);
    expect(text).toContain("2001/2000");
    const alert = container.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain(t.projects.preflight.assets);
    expect(button(t.projects.importNow)!.disabled).toBe(true);
    expect(importProjectZip).not.toHaveBeenCalled();
  });

  it("lets the server decide when the zip cannot be read", async () => {
    index.mockResolvedValueOnce(null);
    await open();
    await chooseZip();
    expect(container.textContent).toContain(t.projects.preflight.readFailed);
    expect(button(t.projects.importNow)!.disabled).toBe(false);
  });

  it("cards show artifacts, applied ones and problems; an unwritable folder disables importing", async () => {
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
    const upload = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent?.includes(t.projects.importProject))!;
    expect(upload.disabled).toBe(true);
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
    expect(button(t.projects.importFirst)).toBeTruthy();     // 049: the empty state imports
    expect(container.textContent).not.toContain("Crea un proyecto");
  });
});
