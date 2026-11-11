import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 064 — the rows behind a card, without leaving the dashboard.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const REPORT = "ventas-layout";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function open(page: Page) {
  await signIn(page);
  await page.goto(`/r/${REPORT}?${SELECTION}`);
  const overlay = page.locator("[aria-busy=true]");
  await expect(overlay).toHaveCount(0);
}

test.describe("view as table", () => {
  test.use({ viewport: { width: 1280, height: 900 }, colorScheme: "light" });

  test("opens from the icon, filters rows and round-trips through ?tabla=", async ({ page }) => {
    await open(page);
    await page.locator('[data-table-action="ranking"]').click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { level: 2 })).toHaveText(/^Datos: /);
    await expect(dialog.getByRole("cell", { name: "Alimento premium" })).toBeVisible();
    await expect(page).toHaveURL(/tabla=ranking/);

    await dialog.getByLabel("Buscar en la tabla").fill("vacuna");
    await expect(dialog.getByRole("cell", { name: "Alimento premium" })).toHaveCount(0);
    await expect(dialog.getByRole("cell", { name: "Vacuna triple" })).toBeVisible();

    await page.reload();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page).not.toHaveURL(/tabla=/);
  });

  test("double-click and T open the same table", async ({ page }) => {
    await open(page);
    const card = page.locator('[data-layout-id="ranking"]');
    await card.dblclick({ position: { x: 10, y: 10 } });
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await card.click({ position: { x: 10, y: 10 } });
    await card.press("t");
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("the maximized card keeps the table across arrows", async ({ page }) => {
    await open(page);
    await page.goto(`/r/${REPORT}?${SELECTION}&ampliar=ranking&tabla=ranking`);
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    const table = dialog.getByRole("button", { name: "Tabla", exact: true });
    await expect(table).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("ArrowRight");
    await expect(page).toHaveURL(/tabla=/);
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("is accessible in both themes", async ({ page }) => {
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await open(page);
      await page.locator('[data-table-action="ranking"]').click();
      const results = await new AxeBuilder({ page }).include("[data-card-dialog]")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
      expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => v.id)).toEqual([]);
    }
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 360, height: 800 } });

  test("the table scrolls inside the dialog, never the page", async ({ page }) => {
    await open(page);
    // Phones keep the menu item, not the icon.
    await page.locator('[data-layout-id="ranking"] button[aria-expanded]').click();
    await page.getByRole("button", { name: "Ver como tabla", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect.poll(() => page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    await expect(page.locator("[data-card-data-scroll]")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tabla", exact: true })).toHaveCount(0);
  });
});
