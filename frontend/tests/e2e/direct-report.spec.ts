// Feature 019, SC-001: hooks stash the seeded workspace, seed app_test_e2e__public.bi_ventas
// + mount golden-direct; restore afterwards.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { reportAction } from "./fixtures/report-action";
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}
async function check(page: Page) {
  // WebKit keeps stale computed styles for a frame after a view change.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}
async function hook<T>(page: Page, path: string, data?: Record<string, unknown>): Promise<T> {
  const r = await page.request.post(path, { headers: FETCH, data });
  expect(r.ok(), `${path} should succeed`).toBe(true);
  return (await r.json()) as T;
}
const kpi = (page: Page, label: string) =>
  page.getByRole("region", { name: "Indicadores" }).getByRole("listitem").filter({ hasText: label });

test.beforeEach(async ({ page }) => {
  const stash = await hook<{ ok: boolean }>(page, "/api/test/workspace/stash");
  expect(stash.ok).toBe(true);
  const seeded = await hook<{ ok: boolean; table: string }>(page, "/api/test/direct/seed");
  expect(seeded.ok).toBe(true);
  expect(seeded.table).toBe("app_test_e2e__public.bi_ventas");
});

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await hook(page, "/api/test/direct/reset");
  await hook(page, "/api/test/workspace/restore");
});

test("direct-only workspace → apply → live dashboard at 375 px → PDF", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);

  await page.goto("/admin/espacio");
  await expect(page.getByRole("heading", { level: 1, name: "Espacio de trabajo" })).toBeVisible();
  await page.getByRole("button", { name: "Validar" }).click();
  await expect(page.getByRole("heading", { name: "Válido" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Aplicar", exact: true }).click();

  const stepUp = page.getByRole("region", { name: "Confirma tu contraseña" });
  await expect(stepUp).toBeVisible();
  await stepUp.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await stepUp.getByRole("button", { name: "Confirmar" }).click();

  const reportItem = page
    .getByRole("listitem")
    .filter({ hasText: "public.bi_ventas" })
    .filter({ has: page.getByText("Directo", { exact: true }) });
  await expect(reportItem).toBeVisible({ timeout: 30_000 });
  await expect(reportItem).toContainText("ventas-directo");

  await check(page);

  await page.setViewportSize({ width: 375, height: 740 });
  await page.goto("/r/ventas-directo");
  await expect(page.getByRole("heading", { level: 1, name: "Ventas directo" })).toBeVisible();
  await expect(kpi(page, "Total vendido")).toContainText(/240,50\sUSD/);
  await expect(page.getByText(/Datos en vivo · BI de esta instalación · consultado/).first()).toBeVisible();

  await check(page);

  const downloadPromise = page.waitForEvent("download");
  await reportAction(page, "Descargar PDF");
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^ventas-directo.*\.pdf$/);
  expect(await download.failure()).toBeNull();
});
