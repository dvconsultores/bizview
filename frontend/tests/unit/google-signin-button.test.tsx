/** Feature 054: the sign-in buttons wear the official marks and match each other's height. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GoogleMark, GoogleSignInButton } from "../../src/components/GoogleSignInButton";
import { t } from "../../src/i18n/es";

// The real provider needs the whole app (auth, branding); the button only asks for the resolved
// theme, so the context is replaced by the one value it reads.
let resolved: "light" | "dark" = "light";
vi.mock("../../src/theme/ThemeContext", () => ({
  useTheme: () => ({
    resolved,
    preference: "system",
    setPreference: async () => undefined,
    palette: "impacto",
    tokens: {},
    setPalette: () => undefined,
  }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

async function render(theme: "light" | "dark") {
  resolved = theme;
  await act(async () => {
    root.render(<GoogleSignInButton onClick={() => undefined} />);
  });
  return container.querySelector('[data-testid="google-sign-in"]') as HTMLButtonElement;
}

describe("GoogleSignInButton", () => {
  it("draws Google's four-colour mark and the catalogue label", async () => {
    const button = await render("light");
    expect(button.textContent).toContain(t.google.signIn);
    const paths = button.querySelectorAll("svg path");
    expect(paths).toHaveLength(4);
    const fills = Array.from(paths).map((path) => path.getAttribute("fill"));
    expect(new Set(fills)).toEqual(new Set(["#EA4335", "#4285F4", "#FBBC05", "#34A853"]));
    expect(button.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("uses the light variant on a light page and the dark one on a dark page", async () => {
    const light = await render("light");
    expect(light.dataset.variant).toBe("light");
    expect(light.className).toContain("bg-[#FFFFFF]");

    const dark = await render("dark");
    expect(dark.dataset.variant).toBe("dark");
    expect(dark.className).toContain("bg-[#131314]");
    // The mark keeps its own colours in both variants.
    expect(dark.querySelectorAll("svg path[fill='#4285F4']")).toHaveLength(1);
  });

  it("is a 44 px touch target with the mark at the left", async () => {
    const button = await render("light");
    expect(button.className).toContain("min-h-tap");
    const first = button.firstElementChild;
    expect(first?.tagName.toLowerCase()).toBe("svg");
  });

  it("calls the opener and exposes the mark on its own for other screens", async () => {
    const onClick = vi.fn();
    await act(async () => {
      root.render(<GoogleSignInButton onClick={onClick} />);
    });
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-testid="google-sign-in"]')!.click();
    });
    expect(onClick).toHaveBeenCalledTimes(1);

    await act(async () => {
      root.render(<GoogleMark />);
    });
    expect(container.querySelectorAll("svg path")).toHaveLength(4);
  });
});
