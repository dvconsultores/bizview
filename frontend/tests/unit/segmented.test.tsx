/**
 * Feature 050, evidence 3 and 4: the appearance choices are one row.
 *
 * The defect these tests exist for: the theme switcher emitted `grid-cols-3` without `grid`, so the
 * three options fell into a block column while the language options sat in a row. The control now
 * owns its layout, so what is asserted here is the property, not a markup snapshot.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

import { SegmentedControl } from "../../src/components/SegmentedControl";

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

async function render(props: Partial<Parameters<typeof SegmentedControl>[0]> = {}) {
  const options = props.options ?? [
    { value: "system", label: "Sistema" },
    { value: "light", label: "Claro" },
    { value: "dark", label: "Oscuro" },
  ];
  const onChange = props.onChange ?? vi.fn();
  await act(async () => {
    root.render(
      <SegmentedControl
        options={options as never}
        value={(props.value ?? "system") as never}
        onChange={onChange as never}
        label={props.label ?? "Apariencia"}
        inMenu={props.inMenu}
        iconOnly={props.iconOnly}
      />,
    );
  });
  return { onChange, options };
}

const group = () => host.querySelector('[role="radiogroup"], [role="group"]') as HTMLElement;
const radios = () => Array.from(host.querySelectorAll<HTMLButtonElement>('[role="radio"], [role="menuitemradio"]'));

describe("SegmentedControl", () => {
  it("puts every option in one grid row", async () => {
    await render();
    // Both halves of the defect matter: `grid` makes the row, `grid-cols-3` sizes it.
    expect(group().className).toContain("grid");
    expect(group().className).toContain("grid-cols-3");
    expect(radios()).toHaveLength(3);
  });

  it("sizes the row from the number of options", async () => {
    await render({ options: [{ value: "es", label: "Español" }, { value: "en", label: "English" }] as never });
    expect(group().className).toContain("grid-cols-2");
  });

  it("has exactly one option checked", async () => {
    await render({ value: "dark" as never });
    const checked = radios().filter((r) => r.getAttribute("aria-checked") === "true");
    expect(checked).toHaveLength(1);
    expect(checked[0].textContent).toBe("Oscuro");
  });

  it("keeps a single tab stop on the checked option", async () => {
    await render({ value: "light" as never });
    const stops = radios().filter((r) => r.tabIndex === 0);
    expect(stops).toHaveLength(1);
    expect(stops[0].textContent).toBe("Claro");
  });

  it("moves and selects with the arrow keys", async () => {
    const { onChange } = await render({ value: "system" as never });
    await act(async () => {
      radios()[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(onChange).toHaveBeenCalledWith("light");
    await act(async () => {
      radios()[2].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(onChange).toHaveBeenLastCalledWith("system");   // wraps to the first option
  });

  it("selects on click", async () => {
    const { onChange } = await render({ value: "system" as never });
    await act(async () => radios()[2].click());
    expect(onChange).toHaveBeenCalledWith("dark");
  });

  it("names the group for a screen reader", async () => {
    await render({ label: "Idioma" });
    expect(group().getAttribute("aria-label")).toBe("Idioma");
  });

  it("inside a menu it is a group of menuitemradio, and the menu owns the keys", async () => {
    const { onChange } = await render({ inMenu: true, value: "system" as never });
    expect(host.querySelector('[role="radiogroup"]')).toBeNull();
    expect(group().getAttribute("role")).toBe("group");
    expect(radios().every((r) => r.getAttribute("role") === "menuitemradio")).toBe(true);
    await act(async () => {
      radios()[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("can hide the labels and keep them as accessible names", async () => {
    await render({
      iconOnly: true,
      options: [
        { value: "light", label: "Claro", icon: () => <svg /> },
        { value: "dark", label: "Oscuro", icon: () => <svg /> },
      ] as never,
      value: "light" as never,
    });
    const [first] = radios();
    expect(first.getAttribute("aria-label")).toBe("Claro");
    expect(first.textContent).toBe("");
  });

  it("uses theme tokens, never a literal colour", async () => {
    await render();
    expect(group().className).toContain("bg-surface-2");
    for (const radio of radios()) {
      expect(radio.className).not.toMatch(/(?:bg|text|ring|border)-(?:red|blue|green|gray|slate|zinc)-/);
    }
  });
});
