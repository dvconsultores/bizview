import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 030 — the report page's filters/parameters sheet (specs/030-report-page-polish).
// The old left panel and the phone "Filtros" view are gone: one non-blocking sheet, two tabs, live
// apply with a 250 ms debounce, chips under the meta line.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

const theme = (page: Page) => page.evaluate(() => document.documentElement.dataset.theme);

const kpi = (page: Page, label: string) =>
  page.getByRole("region", { name: "Indicadores" }).getByRole("listitem").filter({ hasText: label });

/** Filtros opens the sheet; Parámetros opens the compact inline panel (never over the numbers). */
const sheet = (page: Page) => page.getByTestId("report-sheet");
const bar = (page: Page) => page.getByTestId("param-bar");
const filtersSheet = async (page: Page) => {
  await expect(sheet(page)).toBeVisible();
  return sheet(page);
};
const paramsBar = async (page: Page) => {
  await expect(bar(page)).toBeVisible();
  return bar(page);
};

function countDataRequests(page: Page) {
  const state = { count: 0 };
  const listener = (request: { url: () => string }) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/reports/ventas/data") state.count += 1;
  };
  page.on("request", listener);
  return {
    get count() {
      return state.count;
    },
    reset() {
      state.count = 0;
    },
    dispose() {
      page.off("request", listener);
    },
  };
}

async function expectNoHorizontalScroll(page: Page) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
    .toBeLessThanOrEqual(0);
}

async function expectAccessible(
  page: Page,
  where: string,
  { waitIdle = true }: { waitIdle?: boolean } = {},
) {
  if (waitIdle) await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 900 }, colorScheme: "light" });

  test("Parámetros applies live with the dashboard still visible", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    await expect(sheet(page)).toHaveCount(0); // no parameters card, nothing covering the numbers

    const counter = countDataRequests(page);
    counter.reset();

    await page.getByRole("button", { name: "Parámetros", exact: true }).click();
    const params = await paramsBar(page);
    await expect(kpi(page, "Ventas netas")).toBeVisible(); // inline: the numbers stay on screen
    await params.getByLabel("Comparar con").selectOption("previous_year");

    await expect.poll(() => counter.count).toBe(1); // debounced to one request
    await expect(page).toHaveURL(/compare=previous_year/);
    await expect(bar(page)).toBeVisible();
    await expect(kpi(page, "Ventas netas")).toBeVisible();

    // Not a sheet: it closes with its own button, and pressing the action again toggles it.
    await bar(page).getByRole("button", { name: "Cerrar", exact: true }).click();
    await expect(bar(page)).toHaveCount(0);
    counter.dispose();
  });

  test("Filtros: one request per change, chips appear and are removable, Limpiar todo clears", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    const counter = countDataRequests(page);
    await page.getByRole("button", { name: /^Filtros/ }).click();
    const filters = await filtersSheet(page);
    counter.reset();

    await filters.getByRole("combobox", { name: "Producto" }).click();
    await filters.getByRole("option", { name: "Vacuna triple" }).click();

    await expect.poll(() => counter.count).toBe(1);
    await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
    await expect(page).toHaveURL(/filter\.product=Vacuna/);
    await expect(sheet(page)).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }),
    ).toBeVisible();

    await page.reload();
    await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);

    await page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }).click();
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    await expect(page.getByRole("button", { name: /^Quitar filtro/ })).toHaveCount(0);

    await page.getByRole("button", { name: /^Filtros/ }).click();
    await filters.getByRole("button", { name: "Limpiar todo" }).click();
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalScroll(page);
    counter.dispose();
  });

  test("CSV from the card menu and from the sheet's Parámetros tab", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    const [cardDownload] = await Promise.all([
      page.waitForEvent("download"),
      (async () => {
        await page.getByRole("button", { name: "Opciones de Ventas netas por Producto" }).click();
        await page.getByRole("button", { name: "Descargar CSV" }).click();
      })(),
    ]);
    expect(cardDownload.suggestedFilename()).toMatch(/\.csv$/);

    await page.getByRole("button", { name: "Parámetros", exact: true }).click();
    const params = await paramsBar(page);
    const [sheetDownload] = await Promise.all([
      page.waitForEvent("download"),
      (async () => {
        await params.getByRole("radio", { name: "CSV" }).check();
        await params.getByRole("button", { name: "Generar reporte" }).click();
      })(),
    ]);
    expect(sheetDownload.suggestedFilename()).toMatch(/\.csv$/);
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 375, height: 667 }, colorScheme: "light" });

  test("the sheet is a bottom sheet with the dashboard visible above it", async ({ page }) => {
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    await page.getByRole("button", { name: /^Filtros/ }).click();
    const filters = await filtersSheet(page);
    const box = await sheet(page).boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(300); // full width at 375 px
    expect(box!.height).toBeLessThanOrEqual(667 * 0.72);

    await page.keyboard.press("Escape");
    await expect(sheet(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Filtros/ })).toBeFocused();
    await expectNoHorizontalScroll(page);
  });
});

test.describe("accessibility", () => {
  for (const scheme of ["dark", "light"] as const) {
    test.describe(`${scheme} theme`, () => {
      test.use({ colorScheme: scheme });

      test("report, filters sheet, open listbox and parameter panel are accessible", async ({ page }) => {
        await signIn(page);
        await page.goto(`/r/ventas?${SELECTION}&filter.product=Vacuna+triple`);
        await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
        await expect(
          page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }),
        ).toBeVisible();
        expect(await theme(page)).toBe(scheme);

        await expectAccessible(page, "report");
        await expectNoHorizontalScroll(page);

        await page.getByRole("button", { name: /^Filtros/ }).click();
        const filters = await filtersSheet(page);
        await expectAccessible(page, "filters sheet");
        await expectNoHorizontalScroll(page);

        await filters.getByRole("combobox", { name: "Producto" }).click();
        await expect(page.getByRole("listbox")).toBeVisible();
        await expectAccessible(page, "listbox", { waitIdle: false });

        // Esc closes the listbox, then the sheet; the parameter panel is checked at this width.
        await page.keyboard.press("Escape");
        await page.keyboard.press("Escape");
        await expect(sheet(page)).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Parámetros", exact: true })).toBeVisible();
        await page.getByRole("button", { name: "Parámetros", exact: true }).click();
        await paramsBar(page);
        await expectAccessible(page, "parameters panel");
      });
    });
  }
});
