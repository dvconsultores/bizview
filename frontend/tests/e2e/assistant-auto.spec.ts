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

test("the composer offers two modes and Auto switches with one click", async ({ page }) => {
  await signIn(page);
  await newChat(page, "Modos");

  // FR-000 (simplified): a small chip next to the send arrow, two choices, no form.
  const selector = page.locator("[data-mode-selector]");
  await expect(selector).toBeVisible();
  await expect(selector.getByRole("button").first()).toContainText("Auto");
  await axe(page);
  await noOverflow(page);

  await selector.getByRole("button").first().click();
  const menu = page.locator("[data-mode-menu]");
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("menuitemradio")).toHaveCount(2);
  await axe(page);
  await noOverflow(page);

  // Preguntar is immediate and changes the composer's hint.
  await menu.getByRole("menuitemradio", { name: /Preguntar/ }).click();
  await expect(page.locator("[data-mode-pill]")).toContainText("Preguntar");
  await expect(page.getByLabel("Mensaje para el asistente")).toHaveAttribute(
    "placeholder", /Solo lee y explica/,
  );

  // Auto needs no password and shows no panel: one click authorises the run.
  await selector.getByRole("button").first().click();
  await page.locator("[data-mode-menu]").getByRole("menuitemradio", { name: /Auto/ }).click();
  await expect(page.locator("[data-mode-pill]")).toContainText("Auto");
  await expect(page.locator("[data-run-contract]")).toHaveCount(0);
  const row = await page.request.get("/api/assistant/sessions", { headers: FETCH });
  const first = (await row.json()).sessions[0];
  expect(first.mode).toBe("auto");
  expect(first.contract_status).not.toBe("none");
  await axe(page);
});

test("Auto authorises the run without a step-up", async ({ page }) => {
  await signIn(page);
  const { sid } = await newChat(page, "Contrato");

  const id = page.locator("[data-mode-selector]").getByRole("button").first();
  await expect(id).toContainText("Auto");
  await id.click();
  await page.locator("[data-mode-menu]").getByRole("menuitemradio", { name: /Preguntar/ }).click();
  await expect(page.locator("[data-mode-pill]")).toContainText("Preguntar");

  // Back to Auto: the contract is created with the defaults, no password.
  await id.click();
  await page.locator("[data-mode-menu]").getByRole("menuitemradio", { name: /Auto/ }).click();
  await expect
    .poll(async () => {
      const res = await page.request.get(`/api/assistant/sessions/${sid}`, { headers: FETCH });
      return (await res.json()).contract_status;
    })
    .toBe("confirmed");
  const row = await page.request.get(`/api/assistant/sessions/${sid}`, { headers: FETCH });
  const body = await row.json();
  expect(body.mode).toBe("auto");
  expect(body.contract_status).toBe("confirmed");
  expect(body.contract.stages).toEqual(["draft", "preview", "apply"]);
  expect(body.contract.limits.tokens).toBeNull();       // no contract cap
  await expect(page.locator("[data-run-contract]")).toHaveCount(0);
  await noOverflow(page);
});
