// Feature 024 — an image as the report brief (scripted fake provider, test hooks).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII=",
  "base64",
);

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
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id} (${v.help}): ${v.nodes
    .map((n) => `${n.target.join(" ")} :: ${n.failureSummary ?? ""}`.replace(/\n/g, " "))
    .join(" | ")}`)).toEqual([]);
}

async function script(page: Page, steps: unknown[]) {
  const r = await page.request.post("/api/test/assistant/script", { headers: FETCH, data: { steps } });
  expect(r.ok()).toBe(true);
}

async function newProject(page: Page): Promise<string> {
  const r = await page.request.post("/api/projects", {
    headers: FETCH,
    data: { name: `Boceto ${Date.now()}` },
  });
  expect(r.ok()).toBe(true);
  return (await r.json()).slug as string;
}

async function openChat(page: Page, slug: string) {
  await page.goto(`/proyectos/${slug}`);
  // Narrow layouts: the Chat pane. From 1024 px the chat is the docked panel (one chat per screen).
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

test("attach a mockup, accept the notice, send it and find it again after a reload", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  await script(page, [{ text: "He visto el boceto: un reporte por sucursal." }]);
  const composer = await openChat(page, await newProject(page));

  const attach = page.locator("[data-attach]");
  await expect(attach).toBeEnabled();
  await page.locator('input[type="file"]').setInputFiles({
    name: "boceto.png", mimeType: "image/png", buffer: PNG,
  });

  const thumb = page.locator('.flex-1 img[src^="/api/assistant/attachments/"]').first();
  await expect(thumb).toBeVisible({ timeout: 30_000 });

  // The first image send asks once per account: the notice blocks the send until accepted.
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByText("No adjuntes capturas con datos de clientes")).toBeVisible();
  await page.getByRole("button", { name: "Entendido" }).click();

  await expect(page.getByText("He visto el boceto: un reporte por sucursal.")).toBeVisible({
    timeout: 120_000,
  });
  await expect(composer).toHaveValue("");
  const sent = page.locator('a[href^="/api/assistant/attachments/"] img').first();
  await expect(sent).toBeVisible();
  await expect(sent).toHaveAttribute("alt", "boceto.png");

  // The conversation comes back from the server with the image (US4/AS2): a reload lands on the
  // Files tab, so the Chat tab is opened again.
  await page.reload();
  const tab = page.getByRole("tab", { name: "Chat" });
  await expect(tab.or(page.getByLabel("Mensaje para el asistente")).first()).toBeVisible();
  if (await tab.isVisible()) await tab.click();
  await expect(page.locator('a[href^="/api/assistant/attachments/"] img').first()).toBeVisible({
    timeout: 30_000,
  });

  // … and the notice is not asked again (FR-006).
  await page.locator('input[type="file"]').setInputFiles({
    name: "otro.png", mimeType: "image/png", buffer: PNG,
  });
  await expect(page.locator('[aria-label="Bocetos adjuntos"] img')).toHaveCount(1);
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByText("No adjuntes capturas con datos de clientes")).toHaveCount(0);

  await axe(page);
});
