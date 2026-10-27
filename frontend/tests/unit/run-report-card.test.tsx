/** Feature 039: the run report card of a `/speckit-all` plan, next to the conversation. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RunReport } from "../../src/api/types";
import { RunReportCard } from "../../src/components/assistant/RunReportCard";

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

const report: RunReport = {
  spec: "002-ventas",
  path: "specs/002-ventas/run-report.md",
  result: "ready",
  stop_reason: null,
  stages: [
    { stage: "specify", run_id: 4, status: "completed" },
    { stage: "verify", run_id: 9, status: "completed" },
  ],
  pending: ["Aplicar (el contrato no permite `apply`)."],
  decisions: ["- [clarify] Se agrupa por día — es el orden de las historias."],
  verify: [{ check: "validation", ok: true, detail: "" }],
  stories: [{ story: "US1", ok: true, test: "row counts" }],
};

async function render(props: Partial<Parameters<typeof RunReportCard>[0]> = {}) {
  await act(async () => {
    root?.render(<RunReportCard report={report} {...props} />);
  });
}

describe("the run report card (feature 039)", () => {
  it("shows the stages, the decisions and what the human still has to do", async () => {
    await render();
    expect(container.textContent).toContain("specify");
    expect(container.textContent).toContain("verify");
    expect(container.textContent).toContain("Se agrupa por día");
    expect(container.textContent).toContain("US1");
    expect(container.querySelector("[data-run-report-pending]")?.textContent).toContain("Aplicar");
    expect(container.textContent).toContain("Listo para aplicar");
  });

  it("says nothing about pending work when there is none", async () => {
    await render({ report: { ...report, pending: [] } });
    expect(container.querySelector("[data-run-report-pending]")).toBeNull();
  });

  it("opens the report file", async () => {
    const onOpenFile = vi.fn();
    await render({ onOpenFile });
    const button = [...container.querySelectorAll("button")].find((b) =>
      b.textContent?.includes("run-report.md"),
    );
    expect(button).toBeTruthy();
    await act(async () => button!.click());
    expect(onOpenFile).toHaveBeenCalledWith("specs/002-ventas/run-report.md");
  });
});
