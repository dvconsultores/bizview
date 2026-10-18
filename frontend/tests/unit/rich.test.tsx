import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { rich } from "../../src/i18n/rich";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("rich", () => {
  let host: HTMLDivElement;
  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
  });
  afterEach(() => {
    host.remove();
  });

  it("replaces known placeholders", async () => {
    const root = createRoot(host);
    await act(async () => {
      root.render(
        rich("Run {cmd} in {dir}.", { cmd: <code>a</code>, dir: <code>b</code> }),
      );
    });
    expect(host.innerHTML).toBe('Run <code>a</code> in <code>b</code>.');
    act(() => root.unmount());
  });

  it("leaves unknown placeholders as text", async () => {
    const root = createRoot(host);
    await act(async () => {
      root.render(rich("x {missing} y", {}));
    });
    expect(host.innerHTML).toBe("x {missing} y");
    act(() => root.unmount());
  });
});
