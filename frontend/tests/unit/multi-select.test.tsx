import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { MultiSelect } from "../../src/components/MultiSelect";
import axe from "axe-core";
import { t } from "../../src/i18n/es";

async function axeViolations(): Promise<axe.Result[]> {
  const results = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
}

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  container.remove();
  vi.useRealTimers();
});

function Harness({
  initialValues,
  onChange,
  loadOptions,
  max,
  reloadKey,
}: {
  initialValues: string[];
  onChange: (values: string[]) => void;
  loadOptions: (q: string, signal: AbortSignal) => Promise<{ items: string[]; truncated: boolean }>;
  max?: number;
  reloadKey?: string;
}) {
  const [values, setValues] = useState(initialValues);
  return (
    <MultiSelect
      label="Marca"
      values={values}
      onChange={(v) => {
        setValues(v);
        onChange(v);
      }}
      loadOptions={loadOptions}
      max={max}
      reloadKey={reloadKey}
    />
  );
}

function getInput(): HTMLInputElement {
  return container.querySelector("input[role='combobox']") as HTMLInputElement;
}

function getListbox(): HTMLUListElement {
  return container.querySelector("ul[role='listbox']") as HTMLUListElement;
}

function getOptions(): HTMLLIElement[] {
  return Array.from(getListbox().querySelectorAll("li[role='option']"));
}

function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")
    ?.set as (v: string) => void;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

async function renderHarness(
  props: {
    initialValues?: string[];
    loadOptions: (q: string, signal: AbortSignal) => Promise<{ items: string[]; truncated: boolean }>;
    max?: number;
    reloadKey?: string;
    onChange?: (values: string[]) => void;
  },
) {
  const onChange = props.onChange ?? vi.fn();
  await act(async () => {
    root.render(
      <Harness
        initialValues={props.initialValues ?? []}
        loadOptions={props.loadOptions}
        max={props.max}
        reloadKey={props.reloadKey}
        onChange={onChange}
      />,
    );
  });
  return { onChange };
}

describe("MultiSelect", () => {
  it("renders combobox ARIA attributes and label association", async () => {
    const loadOptions = vi.fn(async () => ({ items: [], truncated: false }));
    await renderHarness({ loadOptions });
    const input = getInput();
    expect(input.getAttribute("role")).toBe("combobox");
    expect(input.getAttribute("aria-autocomplete")).toBe("list");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    const label = container.querySelector("label");
    expect(label?.getAttribute("for")).toBe(input.id);
  });

  it("opens on focus, loads options, and renders options with aria-selected", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike", "Adidas"],
      truncated: false,
    }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    expect(loadOptions).toHaveBeenCalledWith("", expect.any(AbortSignal));
    const options = getOptions();
    expect(options).toHaveLength(2);
    expect(options[0].textContent).toBe("Nike");
    expect(options[0].getAttribute("aria-selected")).toBe("false");
    expect(container.querySelector("ul[role='listbox']")?.getAttribute("aria-multiselectable")).toBe(
      "true",
    );
  });

  it("selects multiple values via click and renders chips", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike", "Adidas"],
      truncated: false,
    }));
    const onChange = vi.fn();
    await renderHarness({ loadOptions, onChange });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    const options = getOptions();
    await act(async () => {
      options[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      options[1].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onChange).toHaveBeenLastCalledWith(["Nike", "Adidas"]);
    const buttons = container.querySelectorAll("button[aria-label^='Quitar']");
    expect(buttons).toHaveLength(2);
    expect(buttons[0].getAttribute("aria-label")).toBe("Quitar Nike");
    expect(buttons[1].getAttribute("aria-label")).toBe("Quitar Adidas");
  });

  it("toggles with ArrowDown and Enter, and sets aria-activedescendant", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike", "Adidas", "Puma"],
      truncated: false,
    }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    });
    expect(input.getAttribute("aria-activedescendant")).toContain("-option-1");
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    const buttons = container.querySelectorAll("button[aria-label^='Quitar']");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].getAttribute("aria-label")).toBe("Quitar Adidas");
  });

  it("debounces typing to a single loadOptions call after 250 ms", async () => {
    vi.useFakeTimers();
    const loadOptions = vi.fn(async () => ({ items: [], truncated: false }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    loadOptions.mockClear();
    await act(async () => {
      setInputValue(input, "a");
      setInputValue(input, "ab");
      setInputValue(input, "abc");
    });
    expect(loadOptions).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(250);
    });
    expect(loadOptions).toHaveBeenCalledTimes(1);
    expect(loadOptions).toHaveBeenCalledWith("abc", expect.any(AbortSignal));
  });

  it("closes with Escape", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike"],
      truncated: false,
    }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    expect(getListbox().closest("[hidden]")).toBeNull();
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(getListbox().closest("[hidden]")).not.toBeNull();
  });

  it("removes last value with Backspace on empty query", async () => {
    const loadOptions = vi.fn(async () => ({ items: [], truncated: false }));
    const onChange = vi.fn();
    await renderHarness({ loadOptions, initialValues: ["Nike", "Adidas"], onChange });
    const input = getInput();
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "Backspace", bubbles: true }));
    });
    expect(onChange).toHaveBeenLastCalledWith(["Nike"]);
  });

  it("chip removal button removes one value", async () => {
    const loadOptions = vi.fn(async () => ({ items: [], truncated: false }));
    const onChange = vi.fn();
    await renderHarness({ loadOptions, initialValues: ["Nike", "Adidas"], onChange });
    const removeButtons = container.querySelectorAll("button[aria-label^='Quitar']");
    await act(async () => {
      removeButtons[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onChange).toHaveBeenLastCalledWith(["Adidas"]);
  });

  it("shows noValues when result is empty with blank query", async () => {
    const loadOptions = vi.fn(async () => ({ items: [], truncated: false }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    expect(getListbox().querySelectorAll("[role='option']")).toHaveLength(0);
    expect(container.textContent).toContain("Sin valores en el período");
    expect(container.querySelector("[role='status']")?.textContent).toBe(
      "Sin valores en el período",
    );
  });

  it("shows noMatches when result is empty with a query", async () => {
    vi.useFakeTimers();
    const loadOptions = vi.fn(async () => ({ items: [], truncated: false }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    await act(async () => {
      setInputValue(input, "xyz");
    });
    await act(async () => {
      vi.advanceTimersByTime(250);
    });
    expect(getListbox().querySelectorAll("[role='option']")).toHaveLength(0);
    expect(container.textContent).toContain("Sin coincidencias");
    expect(container.querySelector("[role='status']")?.textContent).toBe(
      "Sin coincidencias",
    );
  });

  it("shows truncated message", async () => {
    const loadOptions = vi.fn(async () => ({ items: ["A"], truncated: true }));
    await renderHarness({ loadOptions });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    expect(container.querySelector("[role='status']")?.textContent).toBe(
      "Se muestran las primeras 200 coincidencias; escribe para acotar.",
    );
  });

  it("blocks selecting beyond max and shows the limit message", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike", "Adidas", "Puma"],
      truncated: false,
    }));
    await renderHarness({ loadOptions, initialValues: ["Nike", "Adidas"], max: 2 });
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    const options = getOptions();
    await act(async () => {
      options[2].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    const selectButtons = container.querySelectorAll("button[aria-label^='Quitar']");
    expect(selectButtons).toHaveLength(2);
    expect(container.querySelector("[role='status']")?.textContent).toBe(
      "Puedes elegir hasta 2 valores.",
    );
  });

  it("reloads when reloadKey changes on next open", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike"],
      truncated: false,
    }));
    const onChange = vi.fn();
    let reloadKey = "key-1";
    const rerender = async (key: string) => {
      reloadKey = key;
      await act(async () => {
        root.render(
          <Harness
            initialValues={[]}
            loadOptions={loadOptions}
            onChange={onChange}
            reloadKey={reloadKey}
          />,
        );
      });
    };
    await rerender("key-1");
    const input = getInput();
    await act(async () => {
      input.focus();
    });
    expect(loadOptions).toHaveBeenCalledTimes(1);
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await act(async () => {
      input.blur();
    });
    await rerender("key-2");
    const input2 = getInput();
    await act(async () => {
      input2.focus();
    });
    expect(loadOptions).toHaveBeenCalledTimes(2);
  });

  it("does not reference a missing listbox while open and empty", async () => {
    const loadOptions = vi.fn(async () => ({ items: [] as string[], truncated: false }));
    await renderHarness({ loadOptions });

    await act(async () => {
      getInput().focus();
    });

    expect(getInput().getAttribute("aria-expanded")).toBe("true");
    const ariaControls = getInput().getAttribute("aria-controls");
    expect(ariaControls).not.toBeNull();
    const controlledElement = document.getElementById(ariaControls!);
    expect(controlledElement).not.toBeNull();
    expect(controlledElement!.getAttribute("role")).toBe("listbox");
    expect(getListbox().querySelectorAll("[role='option']")).toHaveLength(0);
  });

  it("references the rendered listbox when options exist", async () => {
    const loadOptions = vi.fn(async () => ({ items: ["Nike"], truncated: false }));
    await renderHarness({ loadOptions });

    await act(async () => {
      getInput().focus();
    });

    const listbox = getListbox();
    expect(listbox).not.toBeNull();
    expect(getInput().getAttribute("aria-controls")).toBe(listbox!.id);
  });

  it("loading state does not reference a missing listbox", async () => {
    const loadOptions = vi.fn(
      () => new Promise<{ items: string[]; truncated: boolean }>(() => {}),
    );
    await renderHarness({ loadOptions });

    await act(async () => {
      getInput().focus();
    });

    expect(getInput().getAttribute("aria-expanded")).toBe("true");
    const ariaControls = getInput().getAttribute("aria-controls");
    expect(ariaControls).not.toBeNull();
    const controlledElement = document.getElementById(ariaControls!);
    expect(controlledElement).not.toBeNull();
    expect(controlledElement!.getAttribute("role")).toBe("listbox");
    expect(getListbox().querySelectorAll("[role='option']")).toHaveLength(0);
    expect(container.textContent).toContain(t.common.loading);
  });

  it("axe: no serious/critical violations when closed", async () => {
    const loadOptions = vi.fn(async () => ({ items: [] as string[], truncated: false }));
    await renderHarness({ loadOptions });

    const violations = await axeViolations();
    expect(violations.map((violation) => violation.id)).toEqual([]);
  });

  it("axe: no serious/critical violations when open and empty", async () => {
    const loadOptions = vi.fn(async () => ({ items: [] as string[], truncated: false }));
    await renderHarness({ loadOptions });

    await act(async () => {
      getInput().focus();
    });

    const violations = await axeViolations();
    expect(violations.map((violation) => violation.id)).toEqual([]);
  });

  it("axe: no serious/critical violations when open and loading", async () => {
    const loadOptions = vi.fn(
      () => new Promise<{ items: string[]; truncated: boolean }>(() => {}),
    );
    await renderHarness({ loadOptions });

    await act(async () => {
      getInput().focus();
    });

    const violations = await axeViolations();
    expect(violations.map((violation) => violation.id)).toEqual([]);
  });

  it("axe: no serious/critical violations when open with options", async () => {
    const loadOptions = vi.fn(async () => ({
      items: ["Nike", "Adidas"],
      truncated: false,
    }));
    await renderHarness({ loadOptions });

    await act(async () => {
      getInput().focus();
    });

    const violations = await axeViolations();
    expect(violations.map((violation) => violation.id)).toEqual([]);
  });
});
