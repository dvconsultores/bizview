import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { reportAction } from "./fixtures/report-action";

// Feature 005: the backend seeds a workspace (tests.e2e_schema seed): integration
// "ventas-prueba" loaded once, report "ventas" applied.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function check(page: Page) {
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);   // figures settled
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

const kpi = (page: Page, label: string) =>
  page.getByRole("region", { name: "Indicadores" }).getByRole("listitem").filter({ hasText: label });

test("a report renders from its spec: KPIs, trend, ranking, filter, PDF", async ({ page }) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await expect(page.getByRole("heading", { level: 1, name: "Ventas" })).toBeVisible();
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
  await expect(kpi(page, "Pedidos")).toContainText("1");
  await expect(kpi(page, "Ventas netas")).toContainText("Nuevo");            // zero base
  await expect(page.getByRole("heading", { name: "Tendencia: Ventas netas" })).toBeVisible();
  const ranking = page.getByRole("list").filter({ hasText: "Alimento premium" });
  await expect(ranking.getByRole("listitem").first()).toContainText("Alimento premium");
  await check(page);

  await page.getByText("Ver datos").click();
  await expect(page.getByRole("row", { name: /27 sept?\.? 2026/ })).toBeVisible();

  // Feature 030: the filters live in one non-blocking sheet and apply live.
  await page.getByRole("button", { name: /^Filtros/ }).click();
  const filters = page.getByTestId("report-sheet");
  await expect(filters.getByRole("tab", { name: "Filtros" })).toHaveAttribute("aria-selected", "true");
  await filters.getByRole("combobox", { name: "Producto" }).click();
  await filters.getByRole("option", { name: "Vacuna triple" }).click();
  await expect(page).toHaveURL(/filter\.product=Vacuna/);
  await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
  await filters.getByRole("button", { name: "Listo", exact: true }).click();
  await expect(filters).toHaveCount(0);
  await check(page);

  const download = page.waitForEvent("download");
  await reportAction(page, "Descargar PDF");
  expect((await download).suggestedFilename()).toBe("ventas-2026-09-27-2026-09-28.pdf");

  await page.getByRole("button", { name: "Generar resumen" }).click();         // AI is off
  await expect(page.getByRole("alert")).toContainText("La IA no está configurada");
});

test("super user: workspace, integrations and access tokens", async ({ page }, info) => {
  await signIn(page);
  // The workspace has no tile in Administración (the owner does not use it): its address is the way in.
  await page.goto("/admin");
  await expect(page.getByRole("link", { name: /Espacio de trabajo/ })).toHaveCount(0);
  await page.goto("/admin/espacio");
  await expect(page.getByRole("heading", { level: 1, name: "Espacio de trabajo" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Versión activa" })).toBeVisible();
  await page.getByRole("button", { name: "Validar" }).click();
  await expect(page.getByRole("heading", { name: "Válido" })).toBeVisible();
  await check(page);

  await expect(page.getByRole("heading", { name: "Especificaciones" })).toBeVisible();   // feature 011
  await page.getByRole("button", { name: "Ver 001-ventas", exact: true }).click();
  const view = page.getByRole("region", { name: "001-ventas" });
  await expect(view.getByLabel("Especificación", { exact: true })).toContainText("**Spec type**: report");
  await view.getByRole("button", { name: "Plan" }).click();
  await expect(view.getByLabel("Plan", { exact: true })).toContainText("# Plan");
  await check(page);
  await view.getByRole("button", { name: "Volver" }).click();
  await expect(view).toBeHidden();
  await expect(page.getByRole("heading", { level: 1, name: "Espacio de trabajo" })).toBeVisible();

  await page.goto("/admin/integraciones");
  await expect(page.getByRole("heading", { name: "ventas-prueba" })).toBeVisible();
  await expect(page.getByText("Correcta").first()).toBeVisible();
  await page.getByRole("button", { name: "Historial" }).click();
  await expect(page.getByText(/sale_lines: 3 filas/)).toBeVisible();
  await check(page);

  await page.goto("/admin/tokens");
  await page.getByLabel("Nombre").fill(`e2e ${info.project.name}`);
  await page.getByRole("button", { name: "Crear token" }).click();
  const dialog = page.getByRole("region", { name: "Confirma tu contraseña" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await dialog.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.getByText("Copia el token ahora")).toBeVisible();
  await expect(page.locator("code").filter({ hasText: /^bzv_/ })).toBeVisible();
  await check(page);
});
