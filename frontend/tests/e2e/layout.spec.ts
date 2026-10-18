import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 026 — US1: a declared layout.web composes the dashboard
// (specs/026-declarative-layouts/quickstart.md, scenario 1). The seeded workspace declares the
// layout, so every expectation below is read from the API and compared with the rendered DOM
// instead of being hardcoded here.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
/** Seeded with a `layout.web` (KPI + a chart + a bar); the spec fails if it disappears. */
const LAYOUT_REPORT = "ventas-layout";
/** Seeded without a layout: the no-layout contract of FR-009. */
const PLAIN_REPORT = "ventas";
const CUSTOM_SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const DEFAULT_SELECTION = "period=mtd&compare=previous_period";
const CHART_TYPES = ["line", "area", "bar", "pie", "donut"];

interface DeclaredComponent {
  id: string;
  type: string;
  view?: string;
  span?: number;
  summary?: boolean;
}

interface Definition {
  periods?: { allowed?: string[] };
  layout?: { web?: { components?: DeclaredComponent[] } };
}

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

const settled = (page: Page) =>
  page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));

async function definition(page: Page, id: string): Promise<Definition> {
  const response = await page.request.get(`/api/reports/${id}`);
  expect(response.status(), `/api/reports/${id}`).toBe(200);
  return (await response.json()) as Definition;
}

/** The query string the report itself accepts, so the assertions and the page share one selection. */
async function selection(page: Page, id: string): Promise<string> {
  const declared = await definition(page, id);
  return (declared.periods?.allowed ?? []).includes("custom") ? CUSTOM_SELECTION : DEFAULT_SELECTION;
}

async function declaredLayout(page: Page, id: string): Promise<DeclaredComponent[]> {
  return (await definition(page, id)).layout?.web?.components ?? [];
}

async function viewSummaries(page: Page, id: string, query: string): Promise<Record<string, string>> {
  const response = await page.request.get(`/api/reports/${id}/data?${query}`);
  expect(response.status(), `/api/reports/${id}/data`).toBe(200);
  const payload = (await response.json()) as { views: { id?: string; summary?: string }[] };
  return Object.fromEntries(
    payload.views.filter((view) => view.id).map((view) => [view.id as string, view.summary ?? ""]),
  );
}

async function openReport(page: Page, id: string): Promise<Declaration> {
  await signIn(page);
  const query = await selection(page, id);
  const declared = await declaredLayout(page, id);
  await page.goto(`/r/${id}?${query}`);
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  return { query, declared };
}

interface Declaration {
  query: string;
  declared: DeclaredComponent[];
}

async function expectAccessible(page: Page, where: string) {
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

async function expectNoHorizontalScroll(page: Page) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
    .toBeLessThanOrEqual(0);
}

const grid = (page: Page) => page.locator("[data-testid='layout-grid']");
const layoutCells = (page: Page) => page.locator("[data-layout-id]");
const theme = (page: Page) => page.evaluate(() => document.documentElement.dataset.theme);

const declaredIds = (page: Page) =>
  layoutCells(page).evaluateAll((cells) => cells.map((cell) => cell.dataset.layoutId ?? ""));

const gridTracks = (page: Page) =>
  grid(page).evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length);

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test("the declared layout renders in its own order and spans at 375 and 1280 px", async ({ page }) => {
      const { declared } = await openReport(page, LAYOUT_REPORT);
      expect(
        declared.length,
        `${LAYOUT_REPORT} must declare a layout.web for this spec to prove SC-001`,
      ).toBeGreaterThan(0);
      expect(await theme(page)).toBe(scheme);

      // Declared order is the DOM order: the phone layout, the tab order and the reading order match.
      await expect(grid(page)).toBeVisible();
      expect(await declaredIds(page)).toEqual(declared.map((component) => component.id));

      await page.setViewportSize({ width: 375, height: 740 });
      await settled(page);
      expect(await gridTracks(page), "one column on phones").toBe(1);
      const tops = await layoutCells(page).evaluateAll((cells) =>
        cells.map((cell) => Math.round(cell.getBoundingClientRect().top)),
      );
      expect(tops).toEqual([...tops].sort((a, b) => a - b));
      await expectNoHorizontalScroll(page);
      await expectAccessible(page, `layout at 375 in ${scheme}`);

      await page.setViewportSize({ width: 1280, height: 900 });
      await settled(page);
      expect(await gridTracks(page), "twelve columns from the md breakpoint").toBe(12);
      const spans = await layoutCells(page).evaluateAll((cells) =>
        cells.map((cell) => ({ id: cell.dataset.layoutId, column: getComputedStyle(cell).gridColumn })),
      );
      for (const [index, component] of declared.entries()) {
        expect(spans[index].column, component.id).toContain(`span ${component.span ?? 12}`);
      }
      await expectNoHorizontalScroll(page);
      await expectAccessible(page, `layout at 1280 in ${scheme}`);
    });

    test("every chart announces the engine's summary", async ({ page }) => {
      const { query, declared } = await openReport(page, LAYOUT_REPORT);
      expect(await theme(page)).toBe(scheme);

      const charts = declared.filter(
        (component) => CHART_TYPES.includes(component.type) && component.summary !== false,
      );
      expect(charts.length, `${LAYOUT_REPORT} must declare a chart with a summary`).toBeGreaterThan(0);

      const summaries = await viewSummaries(page, LAYOUT_REPORT, query);
      for (const component of charts) {
        const summary = summaries[component.view ?? ""];
        expect(summary, `view ${component.view} of ${component.id}`).toBeTruthy();
        const chart = page.locator(`[data-layout-id="${component.id}"] svg[role='img']`);
        await expect(chart, component.id).toHaveAttribute("aria-label", summary);
        // The same sentence is visible, not only announced.
        await expect(
          page.locator(`[data-layout-id="${component.id}"] figcaption`).first(),
          component.id,
        ).toHaveText(summary);
      }
    });
  });
}

test.describe("without a layout", () => {
  test("the payload order stands and the grid is absent (FR-009)", async ({ page }) => {
    const { declared } = await openReport(page, PLAIN_REPORT);
    expect(declared.length, `${PLAIN_REPORT} must not declare a layout.web`).toBe(0);

    await expect(grid(page)).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Indicadores" })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await expectAccessible(page, `${PLAIN_REPORT} without a layout`);
  });
});
