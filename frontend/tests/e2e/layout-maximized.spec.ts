import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

// Feature 056b — the maximised card must fill the dialog (specs/056-layout-polish FR-008).
// The proof is geometric and is taken at the four widths and in both themes the spec names, in the
// suite's own idiom (`layout.spec.ts` asserts rendered boxes and runs axe; the project keeps no
// visual baselines to compare against). jsdom cannot do this: it has no layout engine, so the unit
// tests stub `clientWidth`/`clientHeight` and these read the real ones.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
/** The seeded workspace only has data in this window; `layout.spec.ts` selects it the same way. */
const CUSTOM_SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const DEFAULT_SELECTION = "period=mtd&compare=previous_period";
/** Seeded with a `layout.web` (KPI + line + horizontal bar + tables); the spec fails if it goes. */
const LAYOUT_REPORT = "ventas-layout";
/** Seeded without a layout: the default rendering also maximises (FR-008, `SingleView`). */
const PLAIN_REPORT = "ventas";
/** The horizontal bar of the production evidence: `BIOLOGICOS PROVIACOL FORTE` and friends. */
const BAR = "ranking";
const SIZES = [375, 768, 1280, 1920] as const;

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

const settled = (page: Page) =>
  page.evaluate(() => new Promise<void>((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));

async function openReport(page: Page, id: string) {
  await signIn(page);
  const response = await page.request.get(`/api/reports/${id}`);
  expect(response.status(), `/api/reports/${id}`).toBe(200);
  const def = (await response.json()) as { periods?: { allowed?: string[] } };
  const query = (def.periods?.allowed ?? []).includes("custom") ? CUSTOM_SELECTION : DEFAULT_SELECTION;
  await page.goto(`/r/${id}?${query}`);
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  await settled(page);
}

/** Clicks a card's Ampliar button and returns the dialog, which carries the only title. */
async function maximize(page: Page, card: Locator) {
  await card.locator("[data-maximize]").click();
  const dialog = page.locator("[data-card-dialog]");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("h2")).toHaveCount(1);
  await expect(dialog.locator("h2")).not.toBeEmpty();
  // An empty view would make every size assertion below vacuously fail: say so plainly.
  await expect(dialog.getByText(/Sin datos|No data/)).toHaveCount(0);
  await settled(page);
  return dialog;
}

interface Box { width: number; height: number }

/** The dialog's content area, the single cell in it and the widest drawing inside that cell. */
async function boxes(page: Page) {
  return page.evaluate(() => {
    const panel = document.querySelector<HTMLElement>("[data-card-dialog]");
    const size = (element: Element | null | undefined) => {
      if (!element) return null;
      const { width, height } = element.getBoundingClientRect();
      return { width, height };
    };
    const area = panel?.querySelector("[data-card-dialog-body]") ?? null;
    const drawings = [...(area?.querySelectorAll("svg, table") ?? [])];
    return {
      body: size(area),
      cell: size(panel?.querySelector("[data-layout-id]") ?? area?.firstElementChild),
      drawing: size(drawings.sort((a, b) =>
        b.getBoundingClientRect().width - a.getBoundingClientRect().width)[0]),
    };
  });
}

/** The dialog only: the dashboard behind it is covered by `layout.spec.ts` at the phone widths. */
async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .include("[data-card-dialog]")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const blocking = results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical");
  expect(
    blocking.map((violation) =>
      `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    for (const width of SIZES) {
      test(`the card fills the dialog at ${width} px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await openReport(page, LAYOUT_REPORT);
        const dialog = await maximize(page, page.locator(`[data-layout-id="${BAR}"]`));

        // `?ampliar=` names the card, so a maximised view can be shared and survives a reload.
        await expect(page).toHaveURL(new RegExp(`ampliar=${BAR}`));

        // One title (the dialog's) and no second set of card controls inside it.
        await expect(dialog.locator("h2")).toHaveCount(1);
        await expect(dialog.locator("[data-maximize]")).toHaveCount(0);
        // `CardMenu`'s trigger is the only `aria-expanded` control a card carries.
        await expect(dialog.locator("button[aria-expanded]")).toHaveCount(0);
        await expect(dialog.locator("[data-layout-id][data-layout-span='12']")).toHaveCount(1);

        const measured = await boxes(page);
        expect(measured.body, "the dialog content area").not.toBeNull();
        expect(measured.cell!.width, "the card spans the dialog").toBeGreaterThan(
          measured.body!.width * 0.9);
        expect(measured.drawing!.width, "the chart spans the card").toBeGreaterThan(
          measured.cell!.width * 0.9);
        expect(measured.drawing!.height, "the chart grows into the dialog").toBeGreaterThan(
          measured.body!.height * 0.5);

        // At the widest sizes no category name is shortened inside the dialog.
        if (width >= 1280) {
          const labels = await dialog.locator("svg text").allTextContents();
          expect(labels.filter((label) => label.endsWith("…"))).toEqual([]);
        }

        await expectAccessible(page);
      });
    }
  });
}

test.describe("every card type", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  for (const [id, name] of [["resumen_kpi", "kpi"], ["tendencia", "line"], ["detalle", "table"]] as const) {
    test(`the ${name} fills the dialog`, async ({ page }) => {
      await openReport(page, LAYOUT_REPORT);
      const dialog = await maximize(page, page.locator(`[data-layout-id="${id}"]`));

      await expect(dialog.locator("h2")).toHaveCount(1);
      await expect(dialog.locator("[data-maximize]")).toHaveCount(0);

      const measured = await boxes(page);
      expect(measured.cell!.width, "the card spans the dialog").toBeGreaterThan(
        measured.body!.width * 0.9);
      expect(measured.cell!.height, "the card fills the height").toBeGreaterThan(
        measured.body!.height * 0.8);
      await expectAccessible(page);
    });
  }

  test("the default ranking card fills the dialog too (no layout)", async ({ page }) => {
    await openReport(page, PLAIN_REPORT);

    const opener = page.locator("[data-maximize]").first();
    await expect(opener).toBeVisible();
    // `Ampliar «Detalle»` / `Enlarge “Detalle”`: the dialog shows the card's own title.
    const label = (await opener.getAttribute("aria-label")) ?? "";
    const name = label.replace(/^.*?[«“]/, "").replace(/[»”]$/, "");
    await opener.click();

    const dialog = page.locator("[data-card-dialog]");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("h2")).toHaveText(name);
    await settled(page);
    await expect(dialog.locator("[data-maximize]")).toHaveCount(0);

    const measured = await boxes(page);
    expect(measured.cell, "the dialog renders the card").not.toBeNull();
    expect(measured.cell!.width, "the default card spans the dialog").toBeGreaterThan(
      measured.body!.width * 0.9);
    expect(measured.cell!.height, "the default card fills the height").toBeGreaterThan(
      measured.body!.height * 0.8);
  });

  test("Back closes the dialog instead of stepping through the cards", async ({ page }) => {
    await openReport(page, LAYOUT_REPORT);
    await maximize(page, page.locator(`[data-layout-id="${BAR}"]`));
    await page.keyboard.press("ArrowRight");
    await settled(page);
    await expect(page.locator("[data-card-dialog] h2")).not.toContainText(BAR);
    await page.goBack();
    await expect(page.locator("[data-card-dialog]")).toHaveCount(0);
    await expect(page).not.toHaveURL(/ampliar=/);
  });
});
