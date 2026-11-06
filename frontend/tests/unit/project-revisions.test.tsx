/** Feature 055: the diff an author confirms, and the revision list with its download and revert. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectDiff, ProjectRevisionList } from "../../src/api/types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const list: ProjectRevisionList = {
  keep: 20,
  applied: 1,
  previous: null,
  items: [
    {
      number: 2, status: "draft", source: "import", files: 7,
      diff: counts({ added: 2, changed: 1 }),
      created_at: "2026-11-05T12:00:00Z", applied_at: null, by: "Super Usuario",
    },
    {
      number: 1, status: "applied", source: "editor", files: 5,
      diff: counts({}),
      created_at: "2026-11-05T09:00:00Z", applied_at: "2026-11-05T09:10:00Z", by: null,
    },
  ],
};

const revert = vi.fn(async () => ({ revision: list.items[0], restored: 1, missing: [] }));
vi.mock("../../src/api/projects", () => ({
  projectsApi: {
    revisions: vi.fn(async () => list),
    revisionZipUrl: (slug: string, number: number) =>
      `/api/projects/${slug}/revisions/${number}/zip`,
    revert: (slug: string, number: number) => revert(slug, number),
  },
}));

function counts(partial: Partial<ProjectDiff["counts"]>) {
  const base = { added: 0, changed: 0, removed: 0, specs_added: 0, specs_removed: 0,
                 ids_added: 0, ids_removed: 0 };
  const merged = { ...base, ...partial };
  return {
    added: Array.from({ length: merged.added }, (_, i) => `new${i}.md`),
    changed: Array.from({ length: merged.changed }, (_, i) => `changed${i}.md`),
    removed: Array.from({ length: merged.removed }, (_, i) => `gone${i}.md`),
    specs: { added: [], removed: [] },
    ids: { added: [], removed: [] },
    counts: merged, truncated: false, base_revision: 1,
  } satisfies ProjectDiff;
}

import { RevisionDiff } from "../../src/components/projects/RevisionDiff";
import { RevisionList } from "../../src/components/projects/RevisionList";
import { t } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  revert.mockClear();
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = null;
  container.remove();
});

const mount = async (node: React.ReactNode) => {
  root = createRoot(container);
  await act(async () => root!.render(node));
};

describe("RevisionDiff", () => {
  it("says what a re-import changes, against which revision", async () => {
    await mount(<RevisionDiff diff={counts({ added: 2, changed: 1 })} mode="reimported"
                              baseRevision={3} />);
    expect(container.textContent).toContain(t.projects.diff.reimportTitle(2, 1, 0, 3));
    expect(container.textContent).toContain(t.projects.diff.fileCounts(2, 1, 0));
    // The paths live behind the disclosure: a 400-file project must not become a wall of text.
    expect(container.querySelector("details")).not.toBeNull();
    expect(container.textContent).toContain("new0.md");
  });

  it("reads a brand new project as everything added", async () => {
    await mount(<RevisionDiff diff={{ ...counts({ added: 4 }), base_revision: null }}
                              mode="created" />);
    expect(container.textContent).toContain(t.projects.diff.createdTitle(4));
  });

  it("says so when the zip changes nothing", async () => {
    await mount(<RevisionDiff diff={counts({})} mode="reimported" />);
    expect(container.textContent).toContain(t.projects.diff.empty);
    expect(container.querySelector("details")).toBeNull();
  });

  it("mentions the truncated list while keeping the exact counts", async () => {
    await mount(<RevisionDiff diff={{ ...counts({ added: 501 }), truncated: true }}
                              mode="reimported" />);
    expect(container.textContent).toContain(t.projects.diff.truncated);
    expect(container.textContent).toContain("+501");
  });
});

describe("RevisionList", () => {
  it("lists the revisions newest first with their source and the chip's numbers", async () => {
    await mount(<RevisionList slug="ventas" />);
    await act(async () => { await Promise.resolve(); });
    const items = Array.from(container.querySelectorAll("li"));
    expect(items[0]?.textContent).toContain(t.projects.revision.number(2));
    expect(items[0]?.textContent).toContain(t.projects.revision.status.draft);
    expect(items[1]?.textContent).toContain(t.projects.revision.status.applied);
    expect(container.textContent).toContain(t.projects.revision.hint(20));
  });

  it("offers a download per revision and a revert only for a non-draft one", async () => {
    await mount(<RevisionList slug="ventas" />);
    await act(async () => { await Promise.resolve(); });
    const links = Array.from(container.querySelectorAll("a"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "/api/projects/ventas/revisions/2/zip",
      "/api/projects/ventas/revisions/1/zip",
    ]);
    // The draft has nothing to restore, so only revision 1 offers the revert.
    const reverts = Array.from(container.querySelectorAll("button"))
      .filter((b) => b.textContent?.includes(t.projects.revision.revert));
    expect(reverts).toHaveLength(1);
  });

  it("asks before reverting, then calls the API", async () => {
    await mount(<RevisionList slug="ventas" />);
    await act(async () => { await Promise.resolve(); });
    const ask = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent?.includes(t.projects.revision.revert))!;
    await act(async () => { ask.click(); });
    expect(container.textContent).toContain(t.projects.revision.revertConfirm(1));
    expect(revert).not.toHaveBeenCalled();

    const confirm = Array.from(container.querySelectorAll("button"))
      .find((b) => b.textContent?.trim() === t.projects.confirm)!;
    await act(async () => { confirm.click(); });
    await act(async () => { await Promise.resolve(); });
    expect(revert).toHaveBeenCalledWith("ventas", 1);
  });
});
