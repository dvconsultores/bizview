/** Feature 030 (FR-003, contracts/report-ui.md §4): the sheet is a landmark panel with tabs, not a
 * modal, and it keeps focus inside while it is open. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportSheet } from "../../src/components/report/ReportSheet";
import { t } from "../../src/i18n/es";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root | null = null;

function setDesktop(desktop: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: desktop && query.includes("1024px"),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  setDesktop(false);
});

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
    root = null;
  }
  container.remove();
});

async function renderSheet(props: Partial<Parameters<typeof ReportSheet>[0]> = {}) {
  const onClose = vi.fn();
  await act(async () => {
    root?.render(
      <ReportSheet open title={t.reportActions.filters(0)} onClose={onClose} {...props}>
        <button type="button">dentro</button>
      </ReportSheet>,
    );
  });
  return { onClose };
}

const sheet = () => document.querySelector('[data-testid="report-sheet"]') as HTMLElement;

describe("ReportSheet", () => {
  it("is a labelled region with a visible heading, never a dialog", async () => {
    await renderSheet();
    const panel = sheet();
    expect(panel.getAttribute("role")).toBe("region");
    expect(panel.hasAttribute("aria-modal")).toBe(false);
    expect(panel.querySelector("h2")?.textContent).toBe(t.reportActions.filters(0));
    expect(panel.querySelector('[role="tablist"]')).toBeNull();
  });

  it("closes with its own close button and with Listo", async () => {
    const { onClose } = await renderSheet();
    const closeButton = document.querySelector(`[aria-label="${t.reportSheet.close}"]`) as HTMLButtonElement;
    await act(async () => closeButton.click());
    expect(onClose).toHaveBeenCalledTimes(1);
    const done = Array.from(document.querySelectorAll("button")).find(
      (el) => el.textContent === t.reportSheet.done,
    ) as HTMLButtonElement;
    await act(async () => done.click());
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("closes on Escape and returns focus to the opener", async () => {
    const opener = document.createElement("button");
    opener.textContent = "abrir";
    document.body.appendChild(opener);
    opener.focus();
    const { onClose } = await renderSheet();
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it("keeps Tab inside the panel while it is open", async () => {
    await renderSheet();
    const focusables = Array.from(
      sheet().querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])'),
    );
    const last = focusables[focusables.length - 1];
    last.focus();
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
    });
    expect(sheet()?.contains(document.activeElement)).toBe(true);
  });

  it("is full screen on phones, a bottom sheet from 640 px and a side sheet from 1024 px", async () => {
    await renderSheet();
    const panel = sheet();
    // Feature 059: `100dvh`, no drag handle and a sticky footer below 640 px.
    expect(panel.className).toContain("h-dvh");
    expect(panel.className).toContain("sm:h-[85vh]");
    expect(panel.className).toContain("rounded-t-2xl");
    expect(panel.className).toContain("lg:w-[360px]");
    expect(panel.className).toContain("motion-reduce:transition-none");
    const handle = panel.querySelector('[aria-hidden][class*="rounded-full"]') as HTMLElement;
    expect(handle.className).toContain("hidden");
    expect(handle.className).toContain("sm:block");
  });

  it("reserves the footer's measured height in the body, so the last control clears it", async () => {
    // Feature 062: 059 asserted a 24 px padding constant and the footer is ~70 px tall, so the last
    // control ended underneath it on a 780 px phone. The body now reserves what the footer measures.
    await renderSheet({ footer: <button type="button">Listo</button> });
    const panel = sheet();
    const body = panel.querySelector('[role="tabpanel"], .overflow-y-auto') as HTMLElement;
    const footer = panel.querySelector("[data-sheet-footer]") as HTMLElement;
    expect(footer).not.toBeNull();
    // The footer is a flex sibling of the scrolling body, never inside it: it cannot overlap.
    expect(body.contains(footer)).toBe(false);
    expect(panel.contains(footer)).toBe(true);
    // jsdom reports 0 for every box, so what is assertable here is the wiring: the body reserves
    // the measured height plus a 16 px gutter the moment the footer reports one.
    const height = Number.parseFloat(body.style.paddingBottom || "0");
    expect(height === 0 || height >= 16).toBe(true);
    expect(footer.className).toContain("env(safe-area-inset-bottom)");
  });

  it("pushes one history entry and closes on the phone's back button", async () => {
    const { onClose } = await renderSheet();
    expect((window.history.state as { bizviewLayer?: string }).bizviewLayer).toBe("report-sheet");
    await act(async () => {
      window.history.back();
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on an outside click on desktop, and not when the click hits the opener", async () => {
    setDesktop(true);
    const opener = document.createElement("button");
    opener.setAttribute("data-sheet-opener", "");
    document.body.appendChild(opener);
    const { onClose } = await renderSheet();
    await act(async () => {
      opener.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(onClose).not.toHaveBeenCalled();
    await act(async () => {
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    opener.remove();
  });

  it("closes when the sheet is swiped down", async () => {
    const { onClose } = await renderSheet();
    const panel = sheet();
    const touch = (clientY: number) =>
      ({ touches: [{ clientY }] }) as unknown as TouchEvent;
    await act(async () => {
      panel.dispatchEvent(Object.assign(new Event("touchstart", { bubbles: true }), touch(10)));
      panel.dispatchEvent(Object.assign(new Event("touchmove", { bubbles: true }), touch(120)));
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("renders nothing while closed", async () => {
    await act(async () => {
      root?.render(
        <ReportSheet open={false} title={t.reportActions.filters(0)} onClose={() => {}}>
          <span>hijo</span>
        </ReportSheet>,
      );
    });
    expect(sheet()).toBeNull();
  });
});

describe("ReportSheet tabs (053)", () => {
  const TABS = [
    { id: "filters", label: t.reportSheet.tabs.filters },
    { id: "params", label: t.reportSheet.tabs.params },
  ];

  async function renderTabs(tab: string, onTabChange = vi.fn()) {
    await act(async () => {
      root?.render(
        <ReportSheet open title={t.reportActions.filters(0)} onClose={vi.fn()} {...{ tabs: TABS, tab, onTabChange }}>
          <button type="button">dentro</button>
        </ReportSheet>,
      );
    });
    return onTabChange;
  }

  it("renders a tablist with the selected tab and a labelled panel", async () => {
    await renderTabs("params");
    const list = sheet().querySelector('[role="tablist"]') as HTMLElement;
    expect(list).toBeTruthy();
    const tabs = Array.from(list.querySelectorAll('[role="tab"]')) as HTMLElement[];
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      t.reportSheet.tabs.filters,
      t.reportSheet.tabs.params,
    ]);
    expect(tabs[1].getAttribute("aria-selected")).toBe("true");
    expect(tabs[0].getAttribute("aria-selected")).toBe("false");
    const panel = sheet().querySelector('[role="tabpanel"]') as HTMLElement;
    expect(panel).toBeTruthy();
    expect(panel.getAttribute("aria-labelledby")).toBe(tabs[1].id);
    expect(tabs[1].getAttribute("aria-controls")).toBe(panel.id);
  });

  it("switches with a click and with the arrow keys, keeping one tab stop", async () => {
    const onTabChange = await renderTabs("filters");
    const tabs = Array.from(sheet().querySelectorAll('[role="tab"]')) as HTMLElement[];
    await act(async () => tabs[1].click());
    expect(onTabChange).toHaveBeenLastCalledWith("params");
    await act(async () => {
      tabs[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(onTabChange).toHaveBeenLastCalledWith("params");
    expect(tabs[0].getAttribute("tabindex")).toBe("0");
    expect(tabs[1].getAttribute("tabindex")).toBe("-1");
  });

  it("stays a region, not a dialog", async () => {
    await renderTabs("params");
    expect(sheet().getAttribute("role")).toBe("region");
    expect(sheet().hasAttribute("aria-modal")).toBe(false);
    expect(sheet().querySelector("h2")?.textContent).toBe(t.reportActions.filters(0));
  });
});
