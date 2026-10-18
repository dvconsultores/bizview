import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn() },
  askReauth: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  },
  qs: (p: Record<string, string | number | undefined | null>) => {
    const parts = Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
    return parts.length ? `?${parts.join("&")}` : "";
  },
}));

import { api } from "../../src/api/client";
import { DiffView } from "../../src/components/ide/DiffView";
import { t } from "../../src/i18n/es";
import { lineDiff } from "../../src/lib/lineDiff";
import { ProjectHistory } from "../../src/pages/projects/ProjectHistory";

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
const flush = async () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const button = (text: string) =>
  Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.trim() === text);

describe("diffs", () => {
  it("renders old/new line numbers and marks changes for screen readers", async () => {
    await act(async () => root.render(
      <DiffView caption="c" truncated hunks={[{ a_start: 4, b_start: 4, lines: [
        { t: " ", text: "x" }, { t: "-", text: "old" }, { t: "+", text: "new" }] }]} />));
    const rows = Array.from(container.querySelectorAll("tbody tr")).map((r) =>
      Array.from(r.querySelectorAll("td")).map((c) => c.textContent));
    expect(rows).toEqual([
      ["4", "4", "", "x"],
      ["5", "", `-${t.projects.removed}`, "old"],
      ["", "5", `+${t.projects.added}`, "new"],
    ]);
    expect(container.textContent).toContain(t.projects.diffTruncated);
  });

  it("client-side line diff of an unsaved buffer", () => {
    const hunks = lineDiff("a\nb\nc\n", "a\nB\nc\n");
    expect(hunks).toEqual([{ a_start: 1, b_start: 1, lines: [
      { t: " ", text: "a" }, { t: "-", text: "b" }, { t: "+", text: "B" }, { t: " ", text: "c" }] }]);
    expect(lineDiff("same\n", "same\n")).toEqual([]);
  });
});

describe("project history page", () => {
  const history = {
    items: [
      { event: "project_applied", time: "2026-10-02T10:00:00Z", actor_name: "Ana", version: 7 },
      { group_id: "g1", actor: "agent", actor_name: null, command: "/speckit-plan", session_id: 3,
        time: "2026-10-01T10:00:00Z",
        files: [{ id: 11, path: "specs/001-a/plan.md", op: "update", actor: "agent", actor_name: null,
                  command: "/speckit-plan", session_id: 3, restored_from: null, renamed_from: null,
                  size: 3, sha256: "s", time: "2026-10-01T10:00:00Z" }] },
    ],
    next_before: null,
  };

  it("lists groups and events, filters by file and restores inline", async () => {
    vi.mocked(api.get).mockImplementation(async (path: string) => {
      if (path === "/api/projects/demo") return { slug: "demo", name: "Demo", origin: "app", specs: [{ folder: "001-a" }] };
      if (path === "/api/projects/demo/tree") return { files: [{ path: "specs/001-a/plan.md", size: 3, sha256: "cur" }] };
      if (path.startsWith("/api/projects/demo/history")) return history;
      throw new Error(`unexpected ${path}`);
    });
    vi.mocked(api.post).mockResolvedValue({ validation: { valid: true, errors: [], warnings: [] },
                                           readiness: { ready: false, pending: [] } });
    await act(async () => root.render(
      <MemoryRouter initialEntries={["/proyectos/demo/historial"]}>
        <Routes><Route path="/proyectos/:slug/historial" element={<ProjectHistory />} /></Routes>
      </MemoryRouter>));
    await flush();
    expect(container.textContent).toContain(t.projects.event.project_applied);
    expect(container.textContent).toContain(t.projects.version(7));
    expect(container.textContent).toContain(t.projects.agent);
    expect(container.textContent).toContain(t.projects.command["speckit-plan"] ?? "/speckit-plan");

    const fileFilter = container.querySelector("select")!;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(fileFilter, "specs/001-a/plan.md");
      fileFilter.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flush();
    expect(vi.mocked(api.get).mock.calls.some(([p]) =>
      p === "/api/projects/demo/history?path=specs%2F001-a%2Fplan.md")).toBe(true);

    await act(async () => button(t.projects.restore)!.click());
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      t.projects.restoreConfirm("specs/001-a/plan.md"));
    expect(api.post).not.toHaveBeenCalled();   // nothing until confirmed
    const confirm = Array.from(container.querySelectorAll('[role="alert"] button')).find(
      (b) => b.textContent?.trim() === t.projects.restore)!;
    await act(async () => (confirm as HTMLButtonElement).click());
    await flush();
    expect(api.post).toHaveBeenCalledWith("/api/projects/demo/history/11/restore", { base_sha256: "cur" });
    expect(container.textContent).toContain(t.projects.restored);
  });
});
