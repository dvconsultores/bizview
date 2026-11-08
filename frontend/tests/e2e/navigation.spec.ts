import { expect, test, type Page } from "@playwright/test";

// Feature 061 — the navigation fixes the owner asked for after using the product: the four counters
// of Inicio open the menu option they count, "Mis listas" left the sidebar (lists live in
// Administración), the lists page carries the app's back control, Apariencia links to the guide that
// explains how to write a theme with any AI, and Proyectos says how to get back to Administración
// when that is where it was opened from.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

test.describe("navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await signIn(page);
  });

  test("every counter of Inicio opens the menu option it counts", async ({ page }) => {
    await page.goto("/");
    const tiles = page.locator('[data-testid="stat-tile-link"]');
    await expect(tiles).toHaveCount(4);
    const hrefs = await tiles.evaluateAll((els) => els.map((el) => el.getAttribute("href")));
    expect(hrefs).toEqual(["/tableros", "/admin/usuarios", "/admin/fuentes", "/admin/integraciones"]);

    await tiles.first().click();
    await expect(page).toHaveURL(/\/tableros$/);
    await page.goBack();
    await tiles.nth(2).click();
    await expect(page).toHaveURL(/\/admin\/fuentes$/);
  });

  test("mailing lists are in Administración, not in the sidebar", async ({ page }) => {
    const sidebar = await page.locator("nav a, aside a").evaluateAll((els) =>
      els.map((el) => el.getAttribute("href")));
    expect(sidebar).not.toContain("/mis-listas");
    await expect(page.getByRole("link", { name: "Mis listas" })).toHaveCount(0);

    // Still reachable where it now belongs, with the same back control as the rest of the app.
    await page.goto("/admin");
    await page.locator("main").getByRole("link", { name: /Listas de correo/ }).click();
    await expect(page).toHaveURL(/\/admin\/listas-de-correo$/);
    const back = page.getByRole("link", { name: "Volver" });
    await expect(back).toBeVisible();
    await expect(back).toHaveAttribute("href", "/admin");
  });

  test("Apariencia links to the guide for creating a theme with your own AI", async ({ page }) => {
    await page.goto("/admin/apariencia");
    const link = page.locator('a[href="/ayuda?tema=temas"]');
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/ayuda\?tema=temas/);
    // The topic is the one that explains the file a theme is, in the interface language.
    await expect(page.locator("main")).toContainText(/tema|theme/i);
  });

  test("Proyectos offers the way back only when it was opened from Administración", async ({ page }) => {
    await page.goto("/admin");
    await page.locator("main").getByRole("link", { name: /Proyectos/ }).click();
    await expect(page).toHaveURL(/\/proyectos$/);
    const back = page.getByRole("link", { name: "Volver" });
    await expect(back).toBeVisible();
    await expect(back).toHaveAttribute("href", "/admin");

    // From the sidebar there is nothing to go back to: the entry is not "inside" Administración.
    await page.goto("/admin");
    await page.locator("nav").first().getByRole("link", { name: "Proyectos" }).click();
    await expect(page).toHaveURL(/\/proyectos$/);
    await expect(page.getByRole("link", { name: "Volver" })).toHaveCount(0);
  });
});
