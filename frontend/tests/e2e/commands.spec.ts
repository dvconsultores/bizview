// Feature 021 T049 — Spec Kit commands in the project chat with the scripted fake provider.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const SPEC = "# Ventas por sucursal\n\n**Tipo**: reporte\n**Status**: Draft\n\nVentas por sucursal y mes.\n";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function axe(page: Page) {
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  // The / menu is a combobox popup: focus stays in the composer and the arrow keys scroll the
  // active option into view (aria-activedescendant), which axe's scrollable-region rule cannot see.
  const comboboxPopup = (n: { html: string }) => n.html.includes("data-command-menu");
  const bad = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => (v.id === "scrollable-region-focusable"
      ? { ...v, nodes: v.nodes.filter((n) => !comboboxPopup(n)) } : v))
    .filter((v) => v.nodes.length > 0);
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function script(page: Page, steps: unknown[]) {
  const r = await page.request.post("/api/test/assistant/script", { headers: FETCH, data: { steps } });
  expect(r.ok()).toBe(true);
}

async function newProject(page: Page): Promise<string> {
  const r = await page.request.post("/api/projects", {
    headers: FETCH,
    data: { name: `Comandos ${Date.now()}` },
  });
  expect(r.ok()).toBe(true);
  return (await r.json()).slug as string;
}

async function openChat(page: Page, slug: string) {
  await page.goto(`/proyectos/${slug}`);
  // Narrow layouts show the Chat pane (the tab must be picked). From 1024 px the chat is the
  // docked panel — one chat per screen since the 024 polish — opened from the project header.
  const chatTab = page.getByRole("tab", { name: "Chat" });
  const toggle = page.getByRole("button", { name: "Asistente", exact: true });
  const composer = page.getByLabel("Mensaje para el asistente");
  await expect(chatTab.or(toggle).or(composer).first()).toBeVisible();
  if (await chatTab.isVisible()) await chatTab.click();
  else if (!(await composer.isVisible())) await toggle.click();
  await expect(composer).toBeVisible();
  return composer;
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/api/test/assistant/reset", { headers: FETCH });
});

test.afterEach(async ({ page }) => {
  await page.request.post("/api/test/assistant/reset", { headers: FETCH });
});

test("/ menu → /speckit-specify → chip and spec; suggestion; off-topic refusal", async ({ page }, info) => {
  test.skip(info.project.name.endsWith("-320"), "flow checked once per engine");
  test.setTimeout(120_000);
  await script(page, [
    { text: "", tool_calls: [{ id: "e1", name: "edit_draft", args: { ops: [
      { op: "write", path: "specs/001-ventas/spec.md", content: SPEC },
    ] } }] },
    { text: "Spec creada.", tool_calls: [{ id: "f1", name: "finish_command", args: { summary: "Spec 001" } }] },
    { text: "", tool_calls: [{ id: "s1", name: "suggest_command", args: { command: "speckit-plan", arguments: "" } }] },
    { text: "El siguiente paso es el plan técnico." },
  ]);
  await signIn(page);
  const slug = await newProject(page);
  const composer = await openChat(page, slug);

  // The / menu: an inline listbox driven from the composer (no dialog).
  await composer.fill("/");
  const menu = page.getByRole("listbox", { name: "Comandos" });
  await expect(menu).toBeVisible();
  await expect(composer).toHaveAttribute("aria-expanded", "true");
  await expect(menu.getByRole("option")).toHaveCount(10);
  await axe(page);
  await composer.press("ArrowDown");
  await composer.press("Enter");
  await expect(composer).toHaveValue("/speckit-specify ");
  await expect(menu).toHaveCount(0);

  await composer.pressSequentially("Reporte de ventas por sucursal");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Ejecutó /speckit-specify en 001-ventas")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator('[data-status="completed"]').first()).toBeVisible();
  const detail = await (await page.request.get(`/api/projects/${slug}`)).json();
  expect(detail.specs.map((s: { folder: string }) => s.folder)).toEqual(["001-ventas"]);

  // Plain message: no file change, an "Insertar" suggestion fills the composer.
  await composer.fill("¿Qué hago ahora?");
  await page.getByRole("button", { name: "Enviar" }).click();
  const insert = page.getByRole("button", { name: "Insertar /speckit-plan en el mensaje" });
  await expect(insert).toBeVisible({ timeout: 60_000 });
  await insert.click();
  await expect(composer).toHaveValue("/speckit-plan ");

  // Off-topic: the fixed refusal, without the AI.
  await composer.fill("Escríbeme un poema sobre el mar");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(/^Solo puedo ayudarte con reportes, integraciones, ETL/)).toBeVisible({ timeout: 30_000 });
  await axe(page);
});

test("desktop: the / menu sits above the composer and passes axe", async ({ page }, info) => {
  test.skip(info.project.name.endsWith("-320"), "checked once per engine");
  await page.setViewportSize({ width: 1280, height: 800 });
  await script(page, []);
  await signIn(page);
  const composer = await openChat(page, await newProject(page));
  await composer.fill("/plan");
  const menu = page.getByRole("listbox", { name: "Comandos" });
  await expect(menu.getByRole("option").first()).toContainText("/speckit-plan");
  await expect(menu.getByText("necesita una spec").first()).toBeVisible();
  await axe(page);
  await composer.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(composer).toHaveValue("/plan");
});
