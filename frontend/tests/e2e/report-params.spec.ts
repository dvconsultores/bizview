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

// Feature 053: Filtros and Parámetros open the same sheet on their own tab; the inline card is gone.
const sheet = (page: Page) => page.getByTestId("report-sheet");
const paramsPanel = (page: Page) => page.getByTestId("report-params-panel");
const filtersSheet = async (page: Page) => {
  await expect(sheet(page)).toBeVisible();
  return sheet(page);
};
const paramsTab = async (page: Page) => {
  await expect(sheet(page)).toBeVisible();
  await expect(paramsPanel(page)).toBeVisible();
  return paramsPanel(page);
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

  test("Parámetros opens the same sheet on its tab and applies live", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    await expect(sheet(page)).toHaveCount(0); // nothing covering the numbers on first paint

    const counter = countDataRequests(page);
    counter.reset();

    await page.getByRole("button", { name: "Parámetros", exact: true }).click();
    const params = await paramsTab(page);
    await expect(sheet(page).getByRole("tab", { name: "Parámetros" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(kpi(page, "Ventas netas")).toBeVisible(); // the numbers stay on screen
    await params.getByLabel("Comparar con").selectOption("previous_year");

    await expect.poll(() => counter.count).toBe(1); // debounced to one request
    await expect(page).toHaveURL(/compare=previous_year/);
    await expect(paramsPanel(page)).toBeVisible();
    await expect(kpi(page, "Ventas netas")).toBeVisible();

    // Filtros switches the same sheet, and the open tab's opener closes it.
    await page.getByRole("button", { name: "Filtros", exact: true }).click();
    await expect(sheet(page).getByRole("tab", { name: "Filtros" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(paramsPanel(page)).toHaveCount(0);
    await page.getByRole("button", { name: "Filtros", exact: true }).click();
    await expect(sheet(page)).toHaveCount(0);
    counter.dispose();
  });

  test("Parámetros → change the period → Listo → the chip is there and a reload keeps it", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    await page.getByRole("button", { name: "Parámetros", exact: true }).click();
    const params = await paramsTab(page);
    await params.getByLabel("Período").selectOption("last_month");
    await expect(page).toHaveURL(/period=last_month/);

    await page.getByRole("button", { name: "Listo" }).click();
    await expect(sheet(page)).toHaveCount(0);
    const chip = page.getByRole("button", { name: "Quitar Período: Mes anterior" });
    await expect(chip).toBeVisible();

    await page.reload();
    await expect(chip).toBeVisible();
    await chip.click();
    await expect(chip).toHaveCount(0);
    await expect(page).not.toHaveURL(/period=last_month/);
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

  test("CSV from the card menu and from the ⋯ menu", async ({ page }, testInfo) => {
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

    const [menuDownload] = await Promise.all([
      page.waitForEvent("download"),
      (async () => {
        await page.getByRole("button", { name: "Más acciones" }).click();
        await expect(page.getByTestId("menu-caption")).toHaveText(
          "Se exporta la selección aplicada.",
        );
        await page.getByRole("menuitem", { name: "Descargar CSV" }).click();
      })(),
    ]);
    expect(menuDownload.suggestedFilename()).toMatch(/\.csv$/);
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 375, height: 667 }, colorScheme: "light" });

  test("the sheet fills the phone screen", async ({ page }) => {
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    await page.getByRole("button", { name: /^Filtros/ }).click();
    const filters = await filtersSheet(page);
    const box = await sheet(page).boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(300); // full width at 375 px
    // Feature 059: no 72 % bottom sheet on a phone — the whole viewport, no wasted quarter.
    expect(Math.round(box!.height)).toBe(667);
    expect(Math.round(box!.y)).toBe(0);

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
        await paramsTab(page);
        await expectAccessible(page, "parameters panel");
      });
    });
  }
});

// Feature 053 (SC-003): the sheet fits its viewport at every width in both themes. The brief asked
// for snapshots; this repository has no visual-snapshot baseline, so the same claim is asserted with
// the checks it already uses: the panel inside the viewport, the dashboard visible behind it and no
// horizontal scroll.
for (const width of [375, 768, 1280, 1920]) {
  for (const scheme of ["light", "dark"] as const) {
    test(`the Parámetros tab fits at ${width}px, ${scheme}`, async ({ page }, testInfo) => {
      test.skip(!testInfo.project.name.startsWith("chromium"), "one engine per width");
      test.setTimeout(60_000);
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ colorScheme: scheme });
      await signIn(page);
      await page.goto(`/r/ventas?${SELECTION}`);
      await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

      await page.getByRole("button", { name: "Parámetros", exact: true }).click();
      const panel = await paramsTab(page);
      const box = await sheet(page).boundingBox();
      expect(box).not.toBeNull();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1);
      // Feature 059 replaced "at most 72 %" with three explicit geometries: full screen on phones,
      // 85 % as a bottom sheet on a tablet, and the full-height side sheet from 1024 px.
      const expectedHeight = width < 640 ? 900 : width < 1024 ? Math.round(900 * 0.85) : 900;
      expect(Math.round(box!.height)).toBe(expectedHeight);
      await expect(panel.getByLabel("Período")).toBeVisible();
      await expectNoHorizontalScroll(page);
      expect(await theme(page)).toBe(scheme);
    });
  }
}
