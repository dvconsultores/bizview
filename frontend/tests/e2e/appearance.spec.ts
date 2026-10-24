import { expect, test, type Page } from "@playwright/test";

// Feature 030 — Administración → Apariencia: the super user picks the installation's palette preset
// and every report follows it (screen and PDF). The preset is restored after each test so the rest
// of the suite keeps the default look.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

test.afterEach(async ({ request }) => {
  await request.put("/api/admin/appearance", {
    headers: FETCH,
    data: { palette_preset: "impacto" },
  });
});

test("the super user picks a preset and every report follows it, in both themes", async ({ page }) => {
  await signIn(page);
  await page.goto("/admin/apariencia");
  await expect(page.getByRole("heading", { level: 1, name: "Apariencia" })).toBeVisible();

  // Five cards, each previewed in both themes.
  await expect(page.getByRole("radio")).toHaveCount(5);
  await expect(page.locator("[data-theme-preview]")).toHaveCount(10);

  await page.getByRole("radio", { name: /Contraste alto/ }).click();
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Paleta guardada.")).toBeVisible();

  // The report page applies it without touching the report definition.
  await page.goto(`/r/ventas?${SELECTION}`);
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.dataset.palette))
    .toBe("contraste");
  const series = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--c-chart-1").trim(),
  );
  expect(series).toBe("11 18 32"); // the `contraste` light series1 (#0B1220)

  // Dark theme keeps the same preset with its dark variant.
  await page.emulateMedia({ colorScheme: "dark" });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.dataset.theme))
    .toBe("dark");
  const darkSeries = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--c-chart-1").trim(),
  );
  expect(darkSeries).toBe("248 250 252"); // #F8FAFC
});

test("a report can preview its own palette from the Parámetros sheet", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await page.getByRole("button", { name: "Parámetros", exact: true }).click();

  const sheetRegion = page.getByTestId("report-sheet");
  await sheetRegion.getByLabel("Paleta").selectOption("daltonico");
  await expect
    .poll(() => page.evaluate(() => document.documentElement.dataset.palette))
    .toBe("daltonico");
  await expect(sheetRegion.getByRole("button", { name: "Copiar para el reporte" })).toBeVisible();
});
