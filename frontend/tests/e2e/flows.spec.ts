import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };

async function signIn(page: Page, email: string, password: string, succeed = true) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  if (succeed) await expect(page).not.toHaveURL(/\/ingresar/);
}

async function signOut(page: Page) {
  await page.goto("/perfil");
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/ingresar/);
}

/** SC-005: no horizontal scrolling at phone widths. */
async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
}

/** SC-005: WCAG 2.2 AA — no serious or critical findings. */
async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => `${n.target.join(" ")} ${n.failureSummary ?? ""}`).join(" | ")}`)).toEqual([]);
}

async function check(page: Page) {
  await expectNoHorizontalScroll(page);
  await expectAccessible(page);
}

test("sign-in page, errors, and protected-route redirect", async ({ page }) => {
  await page.goto("/admin/usuarios");
  await expect(page).toHaveURL(/\/ingresar\?next=%2Fadmin%2Fusuarios/);
  await expect(page.getByRole("heading", { name: "Ingresa a tu cuenta" })).toBeVisible();
  await expect(page).toHaveTitle(/Bizview AI Powered · Cliente Demo/);
  await check(page);

  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page.getByText("Campo obligatorio").first()).toBeVisible();

  await signIn(page, SUPER.email, "wrong-password-x", false);
  await expect(page.getByRole("alert")).toContainText("Correo o contraseña incorrectos");
  await check(page);
});

test("super user: home, profile, users, audit", async ({ page }) => {
  await signIn(page, SUPER.email, SUPER.password);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bienvenido de nuevo, Superusuario");
  await check(page);
  await page.getByRole("link", { name: "Ver todos los tableros" }).click();   // Tableros
  await expect(page.getByRole("heading", { level: 1, name: "Tableros" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: "Ventas" })).toBeVisible();
  await expect(page.getByText("Disponible").first()).toBeVisible();   // applied workspace report
  await check(page);

  await page.goto("/d/ventas");                                        // → /r/ventas
  await expect(page).toHaveURL(/\/r\/ventas/);
  await expect(page.getByRole("heading", { level: 1, name: "Ventas" })).toBeVisible();

  await page.goto("/perfil");
  await expect(page.getByRole("main").getByText("Superusuario").first()).toBeVisible();
  await check(page);

  await page.goto("/admin/usuarios");
  await expect(page.getByRole("heading", { name: "Usuarios" })).toBeVisible();
  await check(page);

  await page.goto("/admin/auditoria");
  await expect(page.getByRole("listitem").getByText("Ingreso", { exact: true }).first()).toBeVisible();
  await check(page);
});

test("super user: AI page (off by default) and source-code footer", async ({ page }) => {
  await signIn(page, SUPER.email, SUPER.password);
  // AGPL-3.0 §13: every page offers version and license (link when a source URL is configured).
  await expect(page.getByRole("contentinfo")).toContainText(/Versión \d+\.\d+\.\d+/);
  await expect(page.getByRole("contentinfo")).toContainText("AGPL-3.0");

  await page.goto("/admin");
  await page.getByRole("link", { name: /Inteligencia artificial/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Inteligencia artificial" })).toBeVisible();
  await expect(page.getByText("Desactivada")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cómo activarla" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Probar conexión" })).toHaveCount(0);
  await check(page);
});

test("create a user, forced password change, grant and revoke access", async ({ page }, info) => {
  const email = `e2e-${info.project.name}-${Date.now()}@example.com`;
  const name = `Paula ${info.project.name}`;
  await signIn(page, SUPER.email, SUPER.password);
  await page.goto("/admin/usuarios/nuevo");
  await check(page);
  await page.getByLabel("Nombre completo").fill(name);
  await page.getByLabel("Correo electrónico").fill(email);
  const temp = await page.getByLabel("Contraseña temporal").inputValue();
  expect(temp).toHaveLength(14);
  await page.getByRole("button", { name: "Crear usuario" }).click();
  const dialog = page.getByRole("region", { name: "Usuario creado." });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(temp);
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Ver usuario" }).click();

  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(page.getByText("Clave temporal")).toBeVisible();
  await check(page);
  const ventas = page.getByRole("switch", { name: "Ventas" });
  await ventas.click();
  await expect(ventas).toHaveAttribute("aria-checked", "true");
  await page.getByRole("button", { name: "Guardar" }).last().click();
  await expect(page.getByText("Acceso actualizado.")).toBeVisible();
  await signOut(page);

  // The new user must replace the temporary password before anything else.
  await signIn(page, email, temp);
  await expect(page).toHaveURL(/\/cambiar-clave/);
  await expect(page.getByRole("heading", { name: "Crea tu contraseña" })).toBeVisible();
  await check(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/cambiar-clave/);
  await page.getByLabel("Contraseña temporal").fill(temp);
  await page.getByLabel("Nueva contraseña", { exact: true }).fill("Paula-nueva-clave-1");
  await page.getByLabel("Confirmar nueva contraseña").fill("Paula-nueva-clave-1");
  await page.getByRole("button", { name: "Cambiar contraseña" }).click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bienvenido de nuevo, Paula");
  await page.getByRole("link", { name: "Ver todos los tableros" }).click();
  await expect(page.getByRole("main").getByRole("link", { name: "Ventas" })).toBeVisible();
  await check(page);

  // Regular users cannot reach administration, by menu or typed address.
  await expect(page.getByRole("link", { name: "Usuarios" })).toHaveCount(0);
  await page.goto("/admin/usuarios");
  await expect(page).toHaveURL(/\/no-autorizado/);
  await expect(page.getByRole("heading", { name: "No autorizado" })).toBeVisible();
  await signOut(page);

  // Revoke → the card disappears and the typed URL is refused.
  await signIn(page, SUPER.email, SUPER.password);
  await page.goto("/admin/usuarios");
  await page.getByLabel("Buscar por nombre o correo").fill(email);
  await expect(page.getByText("1 usuario", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: new RegExp(name) }).first().click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await page.getByRole("switch", { name: "Ventas" }).click();
  await page.getByRole("button", { name: "Guardar" }).last().click();
  await expect(page.getByText("Acceso actualizado.")).toBeVisible();
  await signOut(page);

  await signIn(page, email, "Paula-nueva-clave-1");
  await expect(page.getByText("Aún no tienes tableros asignados")).toBeVisible();
  await page.goto("/d/ventas");
  await expect(page.getByRole("heading", { name: "No autorizado" })).toBeVisible();
});
