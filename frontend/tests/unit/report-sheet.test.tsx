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

  it("is a bottom sheet with a drag handle below 1024 px and a side sheet above", async () => {
    await renderSheet();
    const panel = sheet();
    expect(panel.className).toContain("max-h-[70vh]");
    expect(panel.className).toContain("rounded-t-2xl");
    expect(panel.className).toContain("lg:w-[360px]");
    expect(panel.className).toContain("motion-reduce:transition-none");
    expect(panel.querySelector('[aria-hidden][class*="rounded-full"]')).toBeTruthy();
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
