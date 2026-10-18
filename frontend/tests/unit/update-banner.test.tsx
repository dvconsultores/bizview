/** Feature 025 US2: the notice is dismissible, it is not a modal, and reloading is what takes the
 * person onto the deployed build. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const stale = { value: true };
const reloadApp = vi.fn();
vi.mock("../../src/lib/appVersion", () => ({
  useNewVersion: () => stale.value,
  reloadApp: () => reloadApp(),
}));

import { t } from "../../src/i18n/es";
import { UpdateBanner } from "../../src/components/UpdateBanner";

let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.clearAllMocks();
  stale.value = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

const render = async () => act(async () => root.render(<UpdateBanner />));
const button = (label: string) =>
  Array.from(container.querySelectorAll("button")).find((b) => b.textContent?.includes(label));

describe("the new-version notice", () => {
  it("says a new version is available and offers to reload", async () => {
    await render();
    expect(container.textContent).toContain(t.update.available);
    expect(button(t.update.reload)).toBeTruthy();
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("reloads the app onto the deployed build", async () => {
    await render();
    await act(async () => button(t.update.reload)!.click());
    expect(reloadApp).toHaveBeenCalledTimes(1);
  });

  it("goes away when the person says not now", async () => {
    await render();
    await act(async () => button(t.update.later)!.click());
    expect(container.textContent).not.toContain(t.update.available);
  });

  it("goes away with the dismiss control too", async () => {
    await render();
    const close = container.querySelector("button[aria-label]") as HTMLButtonElement;
    expect(close.getAttribute("aria-label")).toBe(t.update.dismiss);
    await act(async () => close.click());
    expect(container.textContent).not.toContain(t.update.available);
  });

  it("shows nothing while the running build is the deployed one", async () => {
    stale.value = false;
    await render();
    expect(container.textContent).toBe("");
  });
});
