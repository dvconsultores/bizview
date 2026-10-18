import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { totp } from "./totp";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
}

async function check(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function confirmPasswordIfAsked(page: Page, password: string) {
  const dialog = page.getByRole("region", { name: "Confirma tu contraseña" });
  await expect(dialog).toBeVisible();
  await check(page);
  await dialog.getByLabel("Contraseña", { exact: true }).fill(password);
  await dialog.getByRole("button", { name: "Confirmar" }).click();
  await expect(dialog).toBeHidden();
}

test("super user adds a data source: step-up, blocked address, write-only password", async ({ page }, info) => {
  await signIn(page, SUPER.email, SUPER.password);
  await expect(page).not.toHaveURL(/ingresar/);
  await page.goto("/admin");
  await page.getByRole("link", { name: /Fuentes de datos/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Fuentes de datos" })).toBeVisible();
  await check(page);
  await page.getByRole("button", { name: "Nueva fuente" }).click();
  await check(page);
  const name = `Origen ${info.project.name}`;
  await page.getByLabel(/^Nombre\*?$/).fill(name);
  await page.getByLabel(/^Servidor\*?$/).fill("127.0.0.1");
  await page.getByLabel(/^Base de datos\*?$/).fill("ventas");
  await page.getByLabel(/^Usuario\*?$/).fill("bi_ro");
  await page.getByLabel(/^Contraseña\*?$/).fill("Origin-pass-123");
  await page.getByRole("button", { name: "Guardar" }).click();
  await confirmPasswordIfAsked(page, SUPER.password);                    // step-up, then retried
  await expect(page.getByText("Dirección no permitida")).toBeVisible();
  await page.getByLabel(/^Servidor\*?$/).fill("203.0.113.9");
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(page.getByText("Configurada")).toBeVisible();              // never shown again
  await expect(page.locator("input[type=password]")).toHaveCount(0);
  await check(page);
  await page.goto("/admin/seguridad");
  await expect(page.getByRole("heading", { name: /Perfil privado/ })).toBeVisible();
  await check(page);
});

test("a user enables two-step sign-in and signs in with a recovery code", async ({ page }, info) => {
  const email = `mfa-${info.project.name}-${Date.now()}@example.com`;
  const temp = "Temporal-pass-77";
  const final = "Final-pass-9988";
  await signIn(page, SUPER.email, SUPER.password);
  await expect(page).not.toHaveURL(/ingresar/);
  const created = await page.evaluate(async ([e, p]) => {
    const r = await fetch("/api/admin/users", { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
      body: JSON.stringify({ email: e, full_name: "Marta Doble", role: "user", temporary_password: p }) });
    return r.status;
  }, [email, temp]);
  expect(created).toBe(201);
  await page.goto("/perfil");
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/ingresar/);

  await signIn(page, email, temp);
  await expect(page).toHaveURL(/cambiar-clave/);
  await page.getByLabel("Contraseña temporal").fill(temp);
  await page.getByLabel("Nueva contraseña", { exact: true }).fill(final);
  await page.getByLabel("Confirmar nueva contraseña").fill(final);
  await page.getByRole("button", { name: "Cambiar contraseña" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bienvenido de nuevo, Marta");

  await page.goto("/perfil");
  await page.getByRole("link", { name: "Activar" }).click();
  await confirmPasswordIfAsked(page, final);
  const key = (await page.locator(".font-mono.select-all").first().innerText()).replace(/\s/g, "");
  await expect(page.getByRole("img", { name: /Escanea/ })).toBeVisible();
  await check(page);
  await page.getByLabel("Código de verificación").fill(totp(key));
  await page.getByRole("button", { name: "Activar" }).click();
  const codes = page.getByRole("list", { name: /códigos de recuperación/i }).getByRole("listitem");
  await expect(codes).toHaveCount(10);
  const recovery = await codes.first().innerText();
  await check(page);
  await page.getByRole("button", { name: "Ya los guardé" }).click();
  await expect(page.getByText("Activada")).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/ingresar/);

  await signIn(page, email, final);
  await expect(page.getByRole("heading", { name: "Verificación en dos pasos" })).toBeVisible();
  await check(page);
  await page.getByRole("button", { name: "Usar un código de recuperación" }).click();
  await page.getByLabel("Código de recuperación").fill(recovery);
  await page.getByRole("button", { name: "Verificar" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bienvenido de nuevo, Marta");
});
