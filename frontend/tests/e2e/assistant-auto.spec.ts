// Feature 028 — modes and the run contract (composer selector, inline contract panel).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function axe(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function noOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
}

async function resetAssistant(page: Page) {
  const r = await page.request.post("/api/test/assistant/reset", { headers: FETCH });
  expect(r.ok()).toBe(true);
}

/** A project of its own with a conversation open on it: (slug, session id). */
async function newChat(page: Page, label: string): Promise<{ slug: string; sid: number }> {
  await signIn(page);
  await page.goto("/proyectos");
  await page.getByRole("button", { name: "Nuevo proyecto" }).click();
  const form = page.getByRole("form", { name: "Nuevo proyecto" });
  await form.getByLabel("Nombre").fill(`${label} ${Date.now()}`);
  await form.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/[a-z0-9-]+/);
  const slug = new URL(page.url()).pathname.split("/")[2];
  const listed = await page.request.get(`/api/assistant/sessions?project=${slug}`,
                                        { headers: FETCH });
  const items = (await listed.json()).sessions as { id: number }[];
  let sid = items[0]?.id;
  if (!sid) {
    const created = await page.request.post("/api/assistant/sessions",
                                            { headers: FETCH, data: { project: slug } });
    expect(created.ok()).toBe(true);
    sid = (await created.json()).id;
  }
  await page.goto(`/proyectos/${slug}?chat=${sid}`);
  const chatTab = page.getByRole("tab", { name: "Chat" });
  await expect(chatTab.or(page.getByLabel("Mensaje para el asistente")).first()).toBeVisible();
  if (await chatTab.isVisible()) await chatTab.click();
  return { slug, sid };
}

test.beforeEach(async ({ page }) => {
  await resetAssistant(page);
  // The suite runs with AI off: the test hook turns the scripted provider on for this test.
  const scripted = await page.request.post("/api/test/assistant/script",
                                           { headers: FETCH, data: { steps: [] } });
  expect(scripted.ok()).toBe(true);
});

test.afterEach(async ({ page }) => {
  await resetAssistant(page);
});

test("the composer offers the three modes and Auto opens the contract panel", async ({ page }) => {
  await newChat(page, "Modos");

  // FR-000: the selector is a radiogroup with the three modes, Edit by default.
  const selector = page.locator("[data-mode-selector]");
  await expect(selector).toBeVisible();
  await expect(selector.getByRole("radio")).toHaveCount(3);
  await expect(selector.getByRole("radio", { name: "Editar" })).toHaveAttribute(
    "aria-checked", "true",
  );
  await axe(page);
  await noOverflow(page);

  // Switching to Auto only opens the contract: the mode is not active yet.
  await selector.getByRole("radio", { name: "Auto" }).click();
  const contract = page.locator("[data-run-contract]");
  await expect(contract).toBeVisible();
  await expect(contract).toContainText("Contrato del run");
  await expect(contract.getByRole("button", { name: "Autorizar el run" })).toBeDisabled();
  await axe(page);
  await noOverflow(page);

  // Cancelling leaves the mode where it was (the selector says Editar again).
  await contract.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.locator("[data-run-contract]")).toHaveCount(0);
  await expect(selector.getByRole("radio", { name: "Editar" })).toHaveAttribute(
    "aria-checked", "true",
  );

  // Switching down to Preguntar is immediate and changes the composer's hint.
  await selector.getByRole("radio", { name: "Preguntar" }).click();
  await expect(selector.getByRole("radio", { name: "Preguntar" })).toHaveAttribute(
    "aria-checked", "true",
  );
  await expect(page.locator("[data-mode-pill]")).toContainText("Preguntar");
  await expect(page.getByLabel("Mensaje para el asistente")).toHaveAttribute(
    "placeholder", /Solo lee y explica/,
  );
  await axe(page);
});

test("confirming a contract activates Auto and shows the pill", async ({ page }) => {
  const { sid } = await newChat(page, "Contrato");

  await page.locator("[data-mode-selector]").getByRole("radio", { name: "Auto" }).click();
  const contract = page.locator("[data-run-contract]");
  await expect(contract).toContainText("Objetivo");
  await contract.locator('input[type="password"]').fill(SUPER.password);
  await contract.getByRole("button", { name: "Autorizar el run" }).click();
  await expect(page.locator("[data-run-contract]")).toHaveCount(0);

  const row = await page.request.get(`/api/assistant/sessions/${sid}`, { headers: FETCH });
  const body = await row.json();
  expect(body.mode).toBe("auto");
  expect(body.contract_status).toBe("confirmed");
  await expect(page.locator("[data-mode-pill]")).toContainText("Auto");
  await axe(page);
  await noOverflow(page);
});
