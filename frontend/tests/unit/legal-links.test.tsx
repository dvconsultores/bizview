import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../../src/i18n", () => ({
  useT: () => ({ footer: { privacy: "Privacidad", terms: "Términos" } }),
}));

import { LegalLinks } from "../../src/components/LegalLinks";

let container: HTMLDivElement;
let root: Root | null = null;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  container.remove();
});

function render(privacyUrl?: string | null, termsUrl?: string | null) {
  root = createRoot(container);
  act(() => root!.render(<LegalLinks privacyUrl={privacyUrl} termsUrl={termsUrl} />));
}

describe("LegalLinks", () => {
  it("shows nothing when the installation has no legal pages", () => {
    render(null, null);
    expect(container.textContent).toBe("");
    expect(container.querySelectorAll("a")).toHaveLength(0);
  });

  it("links both pages in a new tab", () => {
    render("https://example.com/privacidad/", "https://example.com/terminos/");
    const links = [...container.querySelectorAll("a")];
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["Privacidad", "https://example.com/privacidad/"],
      ["Términos", "https://example.com/terminos/"],
    ]);
    for (const link of links) {
      expect(link.getAttribute("target")).toBe("_blank");
      expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    }
  });

  it("shows the one page that is configured", () => {
    render(null, "https://example.com/terminos/");
    expect(container.querySelectorAll("a")).toHaveLength(1);
    expect(container.textContent).toBe("Términos");
  });
});
