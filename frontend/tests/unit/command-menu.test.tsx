import { act, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CommandDef } from "../../src/api/types";
import { CommandMenu, filterCommands, menuQuery } from "../../src/components/assistant/CommandMenu";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const cmd = (name: string, description: string, needs_spec = true): CommandDef => ({
  name,
  description,
  argument_hint: "",
  needs_spec,
  needs_args: false,
});
const commands = [
  cmd("speckit-specify", "Crea la spec", false),
  cmd("speckit-plan", "Escribe el plan técnico"),
  cmd("speckit-tasks", "Genera tareas a partir del plan"),
];

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

describe("filterCommands", () => {
  it("puts prefix matches (with or without speckit-) before substring matches", () => {
    expect(filterCommands(commands, "plan").map((c) => c.name)).toEqual([
      "speckit-plan",
      "speckit-tasks",
    ]);
    expect(filterCommands(commands, "speckit-t").map((c) => c.name)).toEqual(["speckit-tasks"]);
    expect(filterCommands(commands, "")).toEqual(commands);
    expect(filterCommands(commands, "zzz")).toEqual([]);
  });
});

describe("menuQuery", () => {
  it("only while the caret is in the first token of a / message", () => {
    expect(menuQuery("/spe", 4)).toBe("spe");
    expect(menuQuery("/", 1)).toBe("");
    expect(menuQuery("/speckit-plan x", 15)).toBeNull();
    expect(menuQuery("hola", 2)).toBeNull();
    expect(menuQuery("/spe", 0)).toBeNull();
  });
});

describe("CommandMenu", () => {
  const props = {
    id: "menu",
    activeIndex: 1,
    optionId: (i: number) => `opt-${i}`,
    onActiveChange: () => {},
  };

  it("is a listbox with the active option, badges and a live count", () => {
    const onSelect = vi.fn();
    render(<CommandMenu {...props} items={commands} hasSpec={false} onSelect={onSelect} />);
    const options = container.querySelectorAll<HTMLElement>('[role="listbox"] [role="option"]');
    expect(options).toHaveLength(3);
    expect(options[1].getAttribute("aria-selected")).toBe("true");
    expect(options[0].getAttribute("aria-selected")).toBe("false");
    expect(options[0].textContent).not.toContain(t.assistant.commands.needsSpec);
    expect(options[1].textContent).toContain(t.assistant.commands.needsSpec);
    expect(container.querySelector('[aria-live="polite"]')?.textContent).toBe(
      t.assistant.commands.count(3),
    );
    expect(container.querySelector('[role="dialog"], [aria-modal]')).toBeNull();
    act(() => options[2].click());
    expect(onSelect).toHaveBeenCalledWith(commands[2]);
  });

  it("hides the badge when the conversation has a spec", () => {
    render(<CommandMenu {...props} items={commands} hasSpec onSelect={() => {}} />);
    expect(container.textContent).not.toContain(t.assistant.commands.needsSpec);
  });

  it("says when nothing matches", () => {
    render(<CommandMenu {...props} items={[]} hasSpec onSelect={() => {}} />);
    expect(container.querySelectorAll('[role="option"]')).toHaveLength(0);
    expect(container.textContent).toContain(t.assistant.commands.noMatches);
  });
});
