/** Feature 059 (C): the mobile-first pass on the shell — the top bar, the breadcrumb, the page title
 * block and the report actions row. Widths are measured in `tests/e2e/mobile-first.spec.ts`; here the
 * rules that produce them are pinned. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// The locale provider reads the account's preference, which this file does not exercise.
vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), logout: vi.fn(), refresh: vi.fn() }),
  MFA_SETUP_PATH: "/seguridad/doble-factor",
  safeNext: (next: string | null) => next ?? "/",
}));

import { LocaleProvider } from "../../src/i18n";
import { Breadcrumbs } from "../../src/components/Breadcrumbs";
import { PageHeader } from "../../src/components/PageHeader";
import { es } from "../../src/i18n/es";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  localStorage.setItem("bizview.locale", "es");
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  localStorage.clear();
});

async function render(node: React.ReactNode) {
  await act(async () => {
    root.render(<LocaleProvider><MemoryRouter>{node}</MemoryRouter></LocaleProvider>);
  });
}

describe("the page title block", () => {
  it("uses a 22 px title, a description of at most two lines and a wrapping meta row", async () => {
    await render(<PageHeader title="Proyectos" subtitle="Todo lo que has publicado" badge={<span>3</span>} />);
    const title = container.querySelector("h1") as HTMLElement;
    const subtitle = Array.from(container.querySelectorAll("p"))[0] as HTMLElement;
    expect(title.className).toContain("text-[22px]");
    expect(subtitle.className).toContain("line-clamp-2");
    expect(subtitle.className).toContain("text-sm");
    // The title row wraps instead of overflowing a 360 px screen.
    expect(title.parentElement!.className).toContain("flex-wrap");
  });
});

describe("the breadcrumb", () => {
  it("hides the trail below 480 px and keeps Volver", async () => {
    await render(<Breadcrumbs back="/" items={[{ label: "Proyectos", to: "/proyectos" }, { label: "Ventas" }]} />);
    const trail = container.querySelector("nav") as HTMLElement;
    expect(trail.className).toContain("hidden");
    expect(trail.className).toContain("min-[480px]:block");
    const back = Array.from(container.querySelectorAll("a")).find((a) =>
      a.textContent?.includes(es.common.back),
    ) as HTMLAnchorElement;
    expect(back).toBeTruthy();
    expect(back.className).not.toContain("hidden");
  });
});

describe("the report actions row", () => {
  it("stacks its icon over the label in a 72 px button under 420 px", async () => {
    const { ReportActions } = await import("../../src/components/report/ReportActions");
    await render(
      <ReportActions
        activeFilters={0}
        onOpenFilters={vi.fn()}
        onOpenParams={vi.fn()}
        actions={[]}
      />,
    );
    const row = container.querySelector('[data-testid="report-actions"]') as HTMLElement;
    expect(row.className).toContain("flex-wrap");
    const buttons = Array.from(row.querySelectorAll("button")).filter((b) =>
      b.className.includes("max-[420px]:flex-col"),
    );
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    for (const button of buttons) {
      expect(button.className).toContain("max-[420px]:w-[72px]");
      expect(button.className).toContain("max-[420px]:text-[11px]");
      // The accessible name is still the full label, so the short form is only visual.
      expect(button.getAttribute("aria-label")).toBeTruthy();
    }
  });
});
