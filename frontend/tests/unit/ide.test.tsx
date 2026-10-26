import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

import type { ProjectTree, ProjectValidation } from "../../src/api/types";
import { ConflictBar } from "../../src/components/ide/ConflictBar";
import { EditorTabs, openTab, type OpenTab } from "../../src/components/ide/EditorTabs";
import { Explorer } from "../../src/components/ide/Explorer";
import { PaneTabs } from "../../src/components/ide/PaneTabs";
import { ProblemsPanel } from "../../src/components/ide/ProblemsPanel";
import { StatusBar } from "../../src/components/ide/StatusBar";
import { useLeaveGuard } from "../../src/components/ide/useLeaveGuard";
import { t } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

const render = async (node: React.ReactNode) => act(async () => root.render(node));
const key = async (el: Element, k: string) =>
  act(async () => { el.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true })); });
const button = (text: string) =>
  Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.trim() === text);
/** Icon-only buttons carry their label on aria-label. */
const labelled = (label: string) =>
  Array.from(container.querySelectorAll("button"))
    .find((b) => b.getAttribute("aria-label") === label) as HTMLButtonElement | undefined;

const tree: ProjectTree = {
  files: [
    { path: "project.yaml", size: 10, sha256: "a" },
    { path: "specs/001-ventas/spec.md", size: 10, sha256: "b" },
    { path: "reports/r/report.yaml", size: 10, sha256: "c" },
  ],
  folders: ["specs", "specs/001-ventas", "reports", "reports/r"],
  ignored: [],
  specs: { "specs/001-ventas": { kind: "reporte", stage: "tareas", converged: true } },
  status: "borrador",
};

describe("Explorer", () => {
  it("is a keyboard tree with spec badges", async () => {
    const onOpen = vi.fn();
    const noop = vi.fn(async () => null);
    await render(<Explorer tree={tree} activePath={null} readOnly onOpen={onOpen}
                           onCreate={noop} onRename={noop} onDelete={noop} />);
    const items = () => Array.from(container.querySelectorAll('[role="treeitem"]')) as HTMLElement[];
    expect(container.querySelector('[role="tree"]')?.getAttribute("aria-label")).toBe(t.projects.explorer);
    // Folders first: reports, specs (open by default), then project.yaml.
    expect(items().map((i) => i.textContent)).toEqual(
      expect.arrayContaining(["reports", "project.yaml"]));
    const specs = items().find((i) => i.textContent?.startsWith("specs") && !i.textContent?.includes("001"))!;
    expect(specs.getAttribute("aria-expanded")).toBe("true");
    const folder = items().find((i) => i.textContent?.includes("001-ventas"))!;
    expect(folder.textContent).toContain(t.projects.kind.reporte);
    expect(folder.textContent).toContain(t.projects.stage.tareas);
    expect(folder.textContent).toContain(t.projects.converged);
    expect(items().filter((i) => i.tabIndex === 0)).toHaveLength(1);

    items()[0].focus();
    await key(items()[0], "ArrowDown");
    expect(document.activeElement).toBe(items()[1]);
    await key(folder, "ArrowRight");
    expect(folder.getAttribute("aria-expanded")).toBe("true");
    const spec = items().find((i) => i.textContent === "spec.md")!;
    await key(spec, "Enter");
    expect(onOpen).toHaveBeenCalledWith("specs/001-ventas/spec.md");
    expect(button(t.projects.newFile)).toBeUndefined();   // read-only: no edit actions
  });

  it("creates files inline and shows the server's allowed patterns", async () => {
    const onCreate = vi.fn(async () => "ruta no permitida; rutas permitidas: project.yaml…");
    const noop = vi.fn(async () => null);
    await render(<Explorer tree={tree} activePath={null} readOnly={false} onOpen={vi.fn()}
                           onCreate={onCreate} onRename={noop} onDelete={noop} />);
    await act(async () => button(t.projects.newFile)!.click());
    const input = container.querySelector("input")!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "notes.txt");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => button(t.projects.save)!.click());
    expect(onCreate).toHaveBeenCalledWith("notes.txt", false);
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("rutas permitidas");
  });

  it("F2 renames and Delete asks to delete the focused item; the tree owns only treeitems", async () => {
    const noop = vi.fn(async () => null);
    await render(<Explorer tree={tree} activePath={null} readOnly={false} onOpen={vi.fn()}
                           onCreate={noop} onRename={noop} onDelete={noop} />);
    const item = Array.from(container.querySelectorAll<HTMLElement>('[role="treeitem"]'))
      .find((i) => i.textContent === "project.yaml")!;
    expect(item.getAttribute("aria-keyshortcuts")).toBe("F2 Delete");
    for (const row of Array.from(container.querySelectorAll('[role="tree"] > li'))) {
      const owned = Array.from(row.children).filter((c) => c.getAttribute("aria-hidden") !== "true");
      expect(owned.map((c) => c.getAttribute("role"))).toEqual(["treeitem"]);
    }
    await key(item, "F2");
    expect((container.querySelector("input") as HTMLInputElement).value).toBe("project.yaml");
    await key(item, "Delete");
    expect(container.querySelector("input")).toBeNull();
    expect(button(t.projects.confirm)).toBeDefined();
  });
});

describe("editor tabs", () => {
  it("keeps at most 8 tabs: the oldest clean one closes, all dirty refuses", () => {
    const tabs: OpenTab[] = Array.from({ length: 8 }, (_, i) => ({ path: `f${i}`, dirty: i === 0 }));
    const next = openTab(tabs, "new");
    expect(next.refused).toBe(false);
    expect(next.tabs.map((x) => x.path)).toEqual(["f0", "f2", "f3", "f4", "f5", "f6", "f7", "new"]);
    expect(openTab(tabs, "f3").tabs).toBe(tabs);
    expect(openTab(tabs.map((x) => ({ ...x, dirty: true })), "new").refused).toBe(true);
  });

  it("closing a dirty tab asks inline: save, discard or cancel", async () => {
    const handlers = { onSaveClose: vi.fn(), onDiscardClose: vi.fn(), onCancelClose: vi.fn() };
    await render(<EditorTabs tabs={[{ path: "specs/001-a/spec.md", dirty: true }]} active="specs/001-a/spec.md"
                             onSelect={vi.fn()} onClose={vi.fn()} closing="specs/001-a/spec.md" notice={null}
                             {...handlers} />);
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      t.projects.unsavedClose("specs/001-a/spec.md"));
    expect(container.textContent).toContain(t.projects.unsaved);
    await act(async () => button(t.projects.save)!.click());
    await act(async () => button(t.projects.discard)!.click());
    await act(async () => button(t.projects.cancel)!.click());
    expect(handlers.onSaveClose).toHaveBeenCalledOnce();
    expect(handlers.onDiscardClose).toHaveBeenCalledOnce();
    expect(handlers.onCancelClose).toHaveBeenCalledOnce();
  });
});

describe("problems, status bar and conflicts", () => {
  const validation: ProjectValidation = {
    valid: false,
    errors: [
      { code: "schema_error", message: "falta id", file: "reports/r/report.yaml", line: 3, project: "demo", fix: "agrega id" },
      { code: "duplicate_id", message: "id repetido", file: "projects/otro/reports/x/report.yaml", line: 1, project: "otro" },
    ],
    warnings: [],
    other_projects: { otro: { errors: 1, warnings: 0 } },
  };

  it("a problem of this project opens the file at its line", async () => {
    const onOpen = vi.fn();
    await render(<ProblemsPanel validation={validation} slug="demo" onOpen={onOpen} />);
    expect(container.textContent).toContain(t.projects.problemsCount(1));
    // Feature 037: another project's problem is not rendered, not linked and not fixable.
    expect(container.textContent).not.toContain("id repetido");
    expect(container.textContent).toContain(t.projects.blockedByOthers("otro"));
    const own = Array.from(container.querySelectorAll("button"))
      .filter((b) => b.textContent?.includes("falta id"));
    expect(own).toHaveLength(1);
    await act(async () => own[0].click());
    expect(onOpen).toHaveBeenCalledWith("reports/r/report.yaml", 3);
  });

  it("a problem can be dismissed and brought back", async () => {
    localStorage.clear();
    await render(<ProblemsPanel validation={validation} slug="demo" onOpen={vi.fn()} />);
    expect(container.textContent).toContain(t.projects.problemsCount(1));
    const dismiss = labelled(t.projects.dismissProblem)!;
    await act(async () => dismiss.click());
    expect(container.textContent).not.toContain("falta id");
    expect(container.textContent).toContain(t.projects.dismissedCount(1));
    await act(async () => button(t.projects.showDismissed)!.click());
    expect(container.textContent).toContain("falta id");
    expect(container.textContent).toContain(t.projects.problemsCount(1));
  });

  it("re-checks on demand", async () => {
    const onRevalidate = vi.fn();
    await render(<ProblemsPanel validation={validation} slug="demo" onOpen={vi.fn()}
                                onRevalidate={onRevalidate} />);
    await act(async () => button(t.projects.recheck)!.click());
    expect(onRevalidate).toHaveBeenCalledTimes(1);
  });

  it("status bar states", async () => {
    await render(<StatusBar validation={{ valid: true, errors: [], warnings: [] }}
                            readiness={{ ready: true, pending: [] }} status="cambios"
                            lastApplied={{ version: 7, at: "2026-10-11T10:00:00Z", by: "Ana" }} save="dirty" busy />);
    const bar = container.querySelector('[role="status"]')!;
    for (const text of [t.projects.valid, t.projects.ready, t.projects.status.cambios,
                        t.projects.unsaved, t.projects.agentWorking]) {
      expect(bar.textContent).toContain(text);
    }
    expect(bar.textContent).toMatch(/Versión 7 aplicada .+ por Ana/);     // the last apply (T086)
    await render(<StatusBar validation={validation} readiness={{ ready: false, pending: [] }}
                            status="borrador" lastApplied={null} save="saved" />);
    expect(container.textContent).toContain(t.projects.problemsCount(2));
    expect(container.textContent).toContain(t.projects.notReady);
    expect(container.textContent).toContain(t.projects.neverApplied);
  });

  it("says why the project is not ready, not just that it is not", async () => {
    // Owner, 2026-10-23 ("idk how to apply or preview"): the reason the backend sends was invisible.
    await render(
      <StatusBar validation={{ valid: true, errors: [], warnings: [] }}
                 readiness={{ ready: false, pending: [
                   { code: "preview", file: null, message: "Ejecuta la vista previa." },
                   { code: "query_check", file: "x.yaml", message: "Comprueba este archivo." },
                 ] }}
                 status="borrador" lastApplied={null} save="saved" />,
    );
    const note = container.querySelector("[data-readiness-pending]")!;
    expect(note.textContent).toContain(t.projects.notReady);
    expect(note.textContent).toContain("Ejecuta la vista previa.");
    expect(note.getAttribute("title")).toBe(
      "Ejecuta la vista previa.\nComprueba este archivo.",
    );
  });

  it("turns the pending preview reason into the button that runs it", async () => {
    // "ok but what to do?" (owner, 2026-10-23): the bar said "Ejecuta la vista previa" and stopped
    // there. The reason is now the action.
    const onRunPending = vi.fn();
    await render(
      <StatusBar validation={{ valid: true, errors: [], warnings: [] }}
                 readiness={{ ready: false, pending: [
                   { code: "preview", file: null, message: "Ejecuta la vista previa." }] }}
                 status="borrador" lastApplied={null} save="saved" onRunPending={onRunPending} />,
    );
    const action = container.querySelector("[data-run-pending]") as HTMLButtonElement;
    expect(action).not.toBeNull();
    expect(action.textContent).toBe(t.projects.runPreviewNow);
    await act(async () => action.click());
    expect(onRunPending).toHaveBeenCalledTimes(1);

    // A reason that is not an action (a query check) stays a plain explanation.
    await render(
      <StatusBar validation={{ valid: true, errors: [], warnings: [] }}
                 readiness={{ ready: false, pending: [
                   { code: "query_check", file: "x.yaml", message: "Comprueba este archivo." }] }}
                 status="borrador" lastApplied={null} save="saved" onRunPending={onRunPending} />,
    );
    expect(container.querySelector("[data-run-pending]")).toBeNull();
    expect(container.textContent).toContain("Comprueba este archivo.");
  });

  it("conflict bar choices", async () => {
    const h = { onDiff: vi.fn(), onOverwrite: vi.fn(), onDiscard: vi.fn() };
    await render(<ConflictBar kind="stale" current={{ revision_id: 3, sha256: "x", author: "Ana", time: null }} {...h} />);
    expect(container.textContent).toContain(t.projects.fileChangedBy("Ana", ""));
    await act(async () => button(t.projects.viewDiff)!.click());
    await act(async () => button(t.projects.overwrite)!.click());
    await act(async () => button(t.projects.discardMine)!.click());
    expect([h.onDiff, h.onOverwrite, h.onDiscard].every((f) => f.mock.calls.length === 1)).toBe(true);
  });
});

describe("pane tabs at 375 px", () => {
  it("one pane at a time behind keyboard tabs", async () => {
    const original = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: false, media: q, addEventListener: () => undefined,
                                           removeEventListener: () => undefined })) as unknown as typeof window.matchMedia;
    const onActive = vi.fn();
    await render(<PaneTabs files={<p>F</p>} editor={<p>E</p>} chat={<p>C</p>} active="files" onActive={onActive} />);
    const tabs = Array.from(container.querySelectorAll('[role="tab"]')) as HTMLElement[];
    expect(tabs.map((x) => x.textContent)).toEqual([t.projects.files, t.projects.editor, t.projects.chat]);
    expect(container.querySelector('[role="tabpanel"]')?.textContent).toBe("F");
    await key(tabs[0], "ArrowRight");
    expect(onActive).toHaveBeenCalledWith("editor");
    window.matchMedia = original;
  });
});

describe("leave guard (020 T083)", () => {
  function Page({ active, onBlocked }: { active: boolean; onBlocked: (to: string) => void }) {
    useLeaveGuard(active, onBlocked);
    const location = useLocation();
    return (
      <div>
        <p data-testid="at">{location.pathname}</p>
        <Link to="/tableros">menu</Link>
        <a href="/x.zip" download>zip</a>
      </div>
    );
  }
  const click = async (selector: string) => {
    const el = container.querySelector(selector) as HTMLElement;
    await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 })); });
  };

  it("holds in-app links while tabs are unsaved and lets them through otherwise", async () => {
    const onBlocked = vi.fn();
    await render(<MemoryRouter initialEntries={["/proyectos/demo"]}>
      <Routes><Route path="*" element={<Page active onBlocked={onBlocked} />} /></Routes>
    </MemoryRouter>);
    await click('a[href="/tableros"]');
    expect(onBlocked).toHaveBeenCalledWith("/tableros");
    expect(container.querySelector('[data-testid="at"]')?.textContent).toBe("/proyectos/demo");
    await click("a[download]");
    expect(onBlocked).toHaveBeenCalledTimes(1);           // downloads never leave the page

    await render(<MemoryRouter initialEntries={["/proyectos/demo"]}>
      <Routes><Route path="*" element={<Page active={false} onBlocked={onBlocked} />} /></Routes>
    </MemoryRouter>);
    await click('a[href="/tableros"]');
    expect(container.querySelector('[data-testid="at"]')?.textContent).toBe("/tableros");
    expect(onBlocked).toHaveBeenCalledTimes(1);
  });
});
