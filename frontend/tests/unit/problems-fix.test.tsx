/** Feature 035 (US3, FR-013): a problem the validator can fix carries its own button, so the
 * correction never waits for an AI — the session-23 report goes 1 → 0 problems with one click. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectIssue, ProjectValidation } from "../../src/api/types";
import { ProblemsPanel } from "../../src/components/ide/ProblemsPanel";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  localStorage.clear();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = null;
  container.remove();
});

const joins: ProjectIssue = {
  code: "unjoined_sets",
  message: "Conjuntos sin unión: altseason",
  file: "reports/panorama-cripto/report.yaml",
  line: 12,
  fix: "declara joins: [{left: assets.snapshot_at, right: altseason.snapshot_at}]",
  fix_data: {
    file: "reports/panorama-cripto/report.yaml",
    json_path: "/joins",
    op: "append",
    value: { left: "assets.snapshot_at", right: "altseason.snapshot_at" },
  },
  problem_id: "unjoined_sets:reports/panorama-cripto/report.yaml:/joins",
};
const date: ProjectIssue = {
  code: "date_missing",
  message: "Falta date",
  file: "reports/panorama-cripto/altseason.yaml",
  line: 3,
  fix_data: { file: "reports/panorama-cripto/altseason.yaml", json_path: "/date", op: "set", value: "snapshot_at" },
  problem_id: "date_missing:reports/panorama-cripto/altseason.yaml:/date",
};

function validation(errors: ProjectIssue[]): ProjectValidation {
  return { valid: errors.length === 0, errors, warnings: [] };
}

async function render(props: Parameters<typeof ProblemsPanel>[0]) {
  await act(async () => {
    root?.render(<ProblemsPanel {...props} />);
  });
}

const buttonWith = (text: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent?.includes(text));

describe("applying a deterministic fix (feature 035)", () => {
  it("offers the fix on the problem and sends its identity and its path", async () => {
    const onApplyFix = vi.fn(async () => {});
    await render({ validation: validation([joins]), slug: "cripto", onOpen: () => {}, onApplyFix });
    const button = buttonWith(t.projects.applyFix);
    expect(button).toBeTruthy();
    await act(async () => button!.click());
    expect(onApplyFix).toHaveBeenCalledTimes(1);
    expect(onApplyFix.mock.calls[0][0]).toMatchObject({
      problem_id: joins.problem_id,
      json_path: "/joins",
      op: "append",
    });
    expect(onApplyFix.mock.calls[0][1]).toHaveLength(1);
  });

  it("applies every fix in one step when there is more than one", async () => {
    const onApplyFix = vi.fn(async () => {});
    await render({ validation: validation([joins, date]), slug: "cripto", onOpen: () => {}, onApplyFix });
    const all = buttonWith(t.projects.applyAllFixes(2));
    expect(all).toBeTruthy();
    await act(async () => all!.click());
    expect(onApplyFix).toHaveBeenCalledTimes(1);
    expect(onApplyFix.mock.calls[0][1]).toHaveLength(2);
  });

  it("disables the buttons while a fix is being applied", async () => {
    const onApplyFix = vi.fn(async () => {});
    await render({
      validation: validation([joins, date]),
      slug: "cripto",
      onOpen: () => {},
      onApplyFix,
      applying: true,
    });
    expect(buttonWith(t.projects.applyFix)?.disabled).toBe(true);
    expect(buttonWith(t.projects.applyAllFixes(2))?.disabled).toBe(true);
  });

  it("shows no button for a problem the product cannot fix", async () => {
    const onApplyFix = vi.fn(async () => {});
    const opaque: ProjectIssue = { code: "sql_error", message: "La consulta falla", file: null, line: null };
    await render({ validation: validation([opaque]), slug: "cripto", onOpen: () => {}, onApplyFix });
    expect(buttonWith(t.projects.applyFix)).toBeUndefined();
  });
});
