import { act, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CommandRun } from "../../src/api/types";
import { CommandRunChip } from "../../src/components/assistant/CommandRunChip";
import {
  CommandSuggestions,
  inlineSuggestions,
} from "../../src/components/assistant/CommandSuggestion";
import { SpecPicker } from "../../src/components/assistant/SpecPicker";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement;
function render(el: ReactElement) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => root!.render(el));
}
afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
  root = null;
});
const button = (text: string) =>
  Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes(text));

const run: CommandRun = {
  id: 1,
  message_id: 3,
  command: "speckit-clarify",
  spec: "003-ventas",
  status: "waiting",
  files: [],
  tokens: 0,
  started_at: "2026-10-11T10:00:00Z",
  ended_at: null,
};

describe("CommandRunChip", () => {
  it("waiting run: running title, pill and Terminar", () => {
    const onFinish = vi.fn();
    render(<CommandRunChip run={run} onFinish={onFinish} />);
    expect(container.textContent).toContain("Ejecutando /speckit-clarify en 003-ventas");
    expect(container.querySelector('[data-status="waiting"]')?.textContent).toBe(
      t.assistant.commands.status.waiting,
    );
    act(() => button(t.assistant.commands.finish)!.click());
    expect(onFinish).toHaveBeenCalledTimes(1);
  });

  it("completed run: five files, the rest counted, files open the editor", () => {
    const onOpenFile = vi.fn();
    const paths = ["a.md", "b.md", "a.md", "c.md", "d.md", "b.md", "e.md", "f.md"];
    const files = paths.map((path) => ({ path, action: "write", revision_id: null }));
    render(
      <CommandRunChip
        run={{ ...run, command: "speckit-plan", status: "completed", files }}
        onOpenFile={onOpenFile}
        onFinish={() => {}}
      />,
    );
    expect(container.textContent).toContain("Ejecutó /speckit-plan en 003-ventas");
    const fileButtons = container.querySelectorAll("button[aria-label]");
    expect(fileButtons).toHaveLength(5);
    expect(container.textContent).toContain(t.assistant.commands.moreFiles(1));
    act(() => (fileButtons[0] as HTMLButtonElement).click());
    expect(onOpenFile).toHaveBeenCalledWith("a.md");
    expect(button(t.assistant.commands.finish)).toBeUndefined();
  });

  it("misrouted run shows a warning and re-runs it on the right spec", () => {
    const onRerun = vi.fn();
    render(
      <CommandRunChip
        run={{
          ...run,
          command: "speckit-plan",
          status: "misrouted",
          spec: "001-integracion-facturas",
          misrouted_to: "002-ventas-facturacion",
          arguments: "Plan del reporte",
          files: [],
        }}
        onRerun={onRerun}
      />,
    );
    expect(container.querySelector('[data-status="misrouted"]')?.textContent).toBe(
      t.assistant.commands.status.misrouted,
    );
    expect(container.querySelector("[data-misrouted]")).not.toBeNull();
    expect(button(t.assistant.commands.finish)).toBeUndefined();
    act(() => button(t.assistant.commands.runOnSpec.replace("{spec}", "002-ventas-facturacion"))!.click());
    expect(onRerun).toHaveBeenCalledWith(
      "/speckit-plan 002-ventas-facturacion Plan del reporte ",
    );
  });

  it("interrupted run offers to run it again", () => {
    const onRerun = vi.fn();
    render(
      <CommandRunChip
        run={{ ...run, command: "speckit-implement", status: "interrupted" }}
        onRerun={onRerun}
      />,
    );
    act(() => button(t.assistant.commands.rerun)!.click());
    expect(onRerun).toHaveBeenCalledWith("/speckit-implement ");
  });
});

describe("suggestions", () => {
  it("insert buttons fill the composer text", () => {
    const onInsert = vi.fn();
    render(
      <CommandSuggestions
        items={[{ command: "speckit-plan", arguments: "con ventas" }]}
        onInsert={onInsert}
      />,
    );
    const items = container.querySelectorAll("[data-command-suggestion]");
    expect(items).toHaveLength(1);
    act(() => (items[0] as HTMLButtonElement).click());
    expect(onInsert).toHaveBeenCalledWith("/speckit-plan con ventas ");
  });

  it("finds backticked registry commands in a reply", () => {
    expect(
      inlineSuggestions("Prueba `/speckit-plan con ventas` y `/otra x`", ["speckit-plan"]),
    ).toEqual([{ command: "speckit-plan", arguments: "con ventas" }]);
  });
});

describe("SpecPicker", () => {
  it("lists the project's specs", () => {
    const onPick = vi.fn();
    render(
      <SpecPicker
        command="speckit-plan"
        specs={[{ folder: "001-ventas", title: "Ventas", kind: "reporte", stage: "tareas" }]}
        onPick={onPick}
        onCancel={() => {}}
      />,
    );
    expect(container.textContent).toContain("Ventas · reporte · tareas");
    act(() => button("001-ventas")!.click());
    expect(onPick).toHaveBeenCalledWith("001-ventas");
  });

  it("says when there is none", () => {
    render(<SpecPicker command="speckit-plan" specs={[]} onPick={() => {}} onCancel={() => {}} />);
    expect(container.textContent).toContain(t.assistant.commands.specPickerEmpty);
  });
});
