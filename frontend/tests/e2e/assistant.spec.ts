// Feature 014 — vibe-reporting chat with the scripted fake provider (test hooks).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

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

/** Autonomous runs (feature 017 amendment): the send returns at once; wait for the run to end. */
async function waitIdle(scope: Locator, timeout = 120_000) {
  await expect(scope.locator("[data-session-indicator]")).toBeVisible({ timeout });
  await expect(scope.locator("[data-session-indicator]")).not.toContainText("Trabajando", { timeout });
}

async function resetAssistant(page: Page) {
  const r = await page.request.post("/api/test/assistant/reset", { headers: FETCH });
  expect(r.ok()).toBe(true);
}

test.beforeEach(async ({ page }) => {
  await resetAssistant(page);
});

// The rest of the suite expects the AI to be off.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await resetAssistant(page);
});

// The 014/017 draft → apply → rollback flow now runs on projects with commands:
// projects.spec.ts (SC-001, rollback) and assistant-agent.spec.ts (agent → apply → dashboard).

test.describe("docked panel (desktop)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("top-bar button opens the Customer A-style panel; expand, collapse, Esc closes", async ({ page }, info) => {
    test.skip(info.project.name.endsWith("-320"), "desktop layout checked once per engine");
    test.setTimeout(120_000);
    const scripted = await page.request.post("/api/test/assistant/script", {
      headers: FETCH,
      data: { steps: [{ text: "Hola, ¿qué reporte necesitas?" }] },
    });
    expect(scripted.ok()).toBe(true);

    await signIn(page);
    const toggle = page.getByRole("button", { name: "Abrir asistente" });
    await toggle.click();
    const panel = page.getByRole("complementary", { name: "Asistente" });
    await expect(panel).toBeVisible();
    await expect(panel.getByText(/Hola, soy el asistente de BizView/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Cerrar asistente" }).first()).toHaveAttribute("aria-expanded", "true");
    await check(page);

    await panel.getByLabel("Mensaje para el asistente").fill("Quiero ventas por día");
    await panel.getByLabel("Mensaje para el asistente").press("Enter");
    // 020: the first message of a new chat asks for its project (no modal).
    const proposal = panel.getByRole("region", { name: "¿En qué proyecto trabajamos?" });
    await expect(proposal).toBeVisible();
    await expect(proposal.getByLabel("Nombre")).not.toHaveValue("");
    await check(page);
    await proposal.getByRole("button", { name: "Crear proyecto" }).click();
    await waitIdle(panel);
    await expect(panel.getByText("Hola, ¿qué reporte necesitas?")).toBeVisible({ timeout: 30_000 });
    const userMessage = panel.getByRole("paragraph").filter({ hasText: /^Quiero ventas por día$/ });
    await expect(userMessage).toBeVisible();

    await panel.getByRole("button", { name: "Expandir" }).click();
    await expect(panel.getByRole("button", { name: "Contraer" })).toBeVisible();
    await check(page);
    await panel.getByRole("button", { name: "Contraer" }).click();

    await page.reload();   // remembered per device: still open, same conversation
    await expect(userMessage).toBeVisible();

    // One chat with a conversation list, like an editor's AI chat.
    await panel.getByRole("button", { name: "Nueva conversación" }).click();
    await expect(panel.getByText(/Hola, soy el asistente de BizView/)).toBeVisible();
    await panel.getByRole("button", { name: "Conversaciones" }).click();
    await expect(panel.getByLabel("Buscar conversaciones")).toBeFocused();
    await check(page);
    // Named after its first message, like an editor's AI chat.
    await panel.getByRole("listitem").filter({ hasText: "Quiero ventas por día" })
      .getByRole("button").first().click();
    await expect(panel.getByRole("heading", { name: "Quiero ventas por día" })).toBeVisible();
    await expect(userMessage).toBeVisible();

    await panel.getByLabel("Mensaje para el asistente").press("Escape");
    await expect(panel).toBeHidden();
    await expect(page.getByRole("button", { name: "Abrir asistente" })).toBeFocused();
  });
});
