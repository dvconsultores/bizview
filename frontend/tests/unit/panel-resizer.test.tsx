import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import {
  AssistantPanelProvider,
  clampPanelWidth,
  PANEL_WIDTH,
  PANEL_WIDTH_MAX_RATIO,
  useAssistantPanel,
} from "../../src/components/assistant/AssistantPanelContext";
import { PanelResizer } from "../../src/components/assistant/PanelResizer";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("clampPanelWidth", () => {
  it("keeps the panel between 22 rem and 60 rem", () => {
    expect(clampPanelWidth(100, 1440)).toBe(PANEL_WIDTH.min);
    expect(clampPanelWidth(5000, 1440)).toBe(PANEL_WIDTH.max);
    expect(clampPanelWidth(600, 1440)).toBe(600);
  });

  it("never takes more than 70 % of the screen", () => {
    // A small laptop: 1024 px * 0.7 = 716.8 → 717 px, below the absolute maximum.
    expect(clampPanelWidth(PANEL_WIDTH.max, 1024)).toBe(Math.round(1024 * 0.7));
    expect(clampPanelWidth(900, 1100)).toBe(770);
  });
});

/** Renders the resizer with the real provider so the width lives where the app keeps it. */
function mount() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: Root | undefined;
  let width = 0;
  let setWidth: ((px: number) => void) | null = null;

  function Probe() {
    const panel = useAssistantPanel();
    width = panel.width;
    setWidth = panel.setWidth;
    return <PanelResizer width={panel.width} onResize={panel.setWidth} label="Ancho" />;
  }

  act(() => {
    root = createRoot(container);
    root.render(
      <AssistantPanelProvider>
        <Probe />
      </AssistantPanelProvider>,
    );
  });
  return {
    container,
    get width() {
      return width;
    },
    resize(px: number) {
      act(() => setWidth?.(px));
    },
    unmount: () => {
      act(() => root!.unmount());
      container.remove();
    },
  };
}

describe("PanelResizer", () => {
  it("is a vertical separator the keyboard can drive", () => {
    const view = mount();
    const seam = view.container.querySelector("[data-assistant-resizer]")!;
    expect(seam.getAttribute("role")).toBe("separator");
    expect(seam.getAttribute("aria-orientation")).toBe("vertical");
    expect(seam.getAttribute("tabindex")).toBe("0");

    const start = view.width;
    act(() => {
      seam.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    });
    expect(view.width).toBe(start + 24);
    act(() => {
      seam.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(view.width).toBe(start);
    view.unmount();
  });

  it("Home, End and Enter jump to the limits and back to the default", () => {
    const view = mount();
    const seam = view.container.querySelector("[data-assistant-resizer]")!;
    act(() => {
      seam.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
    });
    expect(view.width).toBe(clampPanelWidth(PANEL_WIDTH.max));
    act(() => {
      seam.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }));
    });
    expect(view.width).toBe(PANEL_WIDTH.min);
    act(() => {
      seam.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    expect(view.width).toBe(PANEL_WIDTH.default);
    view.unmount();
  });

  it("drags: the panel grows when the pointer moves left", () => {
    const view = mount();
    const seam = view.container.querySelector("[data-assistant-resizer]") as HTMLElement;
    const start = view.width;

    act(() => {
      seam.dispatchEvent(
        new PointerEvent("pointerdown", { button: 0, clientX: 900, bubbles: true }),
      );
    });
    act(() => {
      window.dispatchEvent(new PointerEvent("pointermove", { clientX: 780 }));
    });
    expect(view.width).toBe(clampPanelWidth(start + 120));
    act(() => {
      window.dispatchEvent(new PointerEvent("pointerup", {}));
    });
    // After the pointer is released the panel stays where it was dropped.
    act(() => {
      window.dispatchEvent(new PointerEvent("pointermove", { clientX: 400 }));
    });
    expect(view.width).toBe(clampPanelWidth(start + 120));
    view.unmount();
  });

  it("shrinks with the window when the remembered width no longer fits", () => {
    const view = mount();
    view.resize(PANEL_WIDTH.max);
    const wide = clampPanelWidth(PANEL_WIDTH.max);
    expect(view.width).toBe(wide);

    const original = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { value: 800, configurable: true });
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(view.width).toBe(Math.min(wide, Math.round(800 * PANEL_WIDTH_MAX_RATIO)));
    Object.defineProperty(window, "innerWidth", { value: original, configurable: true });
    view.unmount();
  });

  it("remembers the width of the device", () => {
    const view = mount();
    view.resize(400);
    expect(localStorage.getItem("bizview.assistantPanel.width")).toBe("400");
    view.unmount();

    const again = mount();
    expect(again.width).toBe(400);
    again.unmount();
  });
});
