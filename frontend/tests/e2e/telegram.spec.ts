import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 007. Telegram is simulated through the backend's test hooks (BIZVIEW_TEST_HOOKS=1 in
// backend.sh): updates are fed to the real conversation handler; nothing reaches Telegram.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const FROM = { id: 7001, first_name: "Ana", last_name: "E2E", username: "ana_e2e" };
let updateCounter = 0;
const nextUpdateId = () => ++updateCounter;

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
  // Confirm the password up front (5-minute step-up window): no dialog races in the flows below.
  const r = await page.request.post("/api/auth/reauth", { headers: FETCH, data: { password: SUPER.password } });
  expect(r.status()).toBe(204);
}

async function confirmPasswordIfAsked(page: Page, password: string) {
  const dialog = page.getByRole("region", { name: "Confirma tu contraseña" });
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByLabel("Contraseña", { exact: true }).fill(password);
    await dialog.getByRole("button", { name: "Confirmar" }).click();
    await expect(dialog).toBeHidden();
  }
}

// WebKit may report stale computed styles right after a theme switch, so wait two animation frames after the dataset changes.
async function themeApplied(page: Page, theme: "light" | "dark") {
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe(theme);
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

async function expectAccessible(page: Page, where: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function sendStart(page: Page, token: string) {
  const r = await page.request.post("/api/test/telegram/update", {
    headers: FETCH,
    data: { update_id: nextUpdateId(), message: { message_id: 1, from: FROM, chat: { id: 7001, type: "private" }, date: 0, text: `/start ${token}` } },
  });
  expect(r.ok()).toBeTruthy();
}

async function press(page: Page, data: string) {
  const id = nextUpdateId();
  const r = await page.request.post("/api/test/telegram/update", {
    headers: FETCH,
    data: { update_id: id, callback_query: { id: `cb${id}`, from: FROM, message: { message_id: 1, chat: { id: 7001, type: "private" }, date: 0, text: "" }, data } },
  });
  expect(r.ok()).toBeTruthy();
}

async function lastButtons(page: Page): Promise<string[]> {
  const sent = (await (await page.request.get("/api/test/telegram/sent")).json()) as Array<{ reply_markup?: { inline_keyboard: { callback_data: string }[][] } }>;
  for (let i = sent.length - 1; i >= 0; i--) {
    const kb = sent[i]?.reply_markup?.inline_keyboard;
    if (kb?.length) return kb.flat().map((b) => b.callback_data);
  }
  return [];
}

async function tokenFromOpenLink(page: Page): Promise<string> {
  const link = page.getByRole("link", { name: "Abrir Telegram" });
  await expect(link).toBeVisible();
  return (await link.getAttribute("href"))!.split("start=")[1];
}

async function configureBot(page: Page) {
  await signIn(page);
  await page.goto("/admin/seguridad");
  await page.getByLabel("Nombre del bot").fill("BizviewE2eBot");
  await page.getByLabel("Credencial del bot").fill("123456789:AAE2E-test-credential-0001");
  await page.getByRole("button", { name: "Guardar" }).click();
  await confirmPasswordIfAsked(page, SUPER.password);
  await expect(page.getByText("Configurada", { exact: true })).toBeVisible();
  await page.request.post("/api/test/telegram/check-ok", { headers: FETCH });
  await page.reload();
  const switcher = page.getByRole("switch", { name: "Activar ingreso con Telegram" });
  await expect(switcher).toBeEnabled();
  await switcher.click();
  await confirmPasswordIfAsked(page, SUPER.password);
  await expect(switcher).toHaveAttribute("aria-checked", "true");
}

async function linkOwnTelegram(page: Page) {
  await page.goto("/perfil");
  await page.getByRole("button", { name: "Vincular Telegram" }).click();
  await confirmPasswordIfAsked(page, SUPER.password);
  await sendStart(page, await tokenFromOpenLink(page));
  await press(page, (await lastButtons(page)).find((b) => b.startsWith("ok:"))!);
  await expect(page.getByText("Vinculado como Ana E2E")).toBeVisible({ timeout: 10_000 });
}

async function startTelegramSignIn(page: Page): Promise<{ code: string; token: string }> {
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/ingresar/);
  await page.getByRole("button", { name: "Ingresar con Telegram" }).click();
  const codeEl = page.locator("p.text-5xl");
  await expect(codeEl).toBeVisible();
  const code = (await codeEl.textContent())!.trim();
  return { code, token: await tokenFromOpenLink(page) };
}

test.beforeEach(async ({ request }) => {
  await request.post("/api/test/telegram/reset", { headers: FETCH });
});

test.afterEach(async ({ request }) => {
  await request.post("/api/test/telegram/reset", { headers: FETCH });
});

test("super user configures, links and signs in with Telegram", async ({ page }) => {
  test.slow();
  await configureBot(page);
  await expectAccessible(page, "admin card");

  await linkOwnTelegram(page);
  await expectAccessible(page, "profile card");

  const { code, token } = await startTelegramSignIn(page);
  await expectAccessible(page, "sign-in panel light");
  await page.emulateMedia({ colorScheme: "dark" });
  await themeApplied(page, "dark");
  await expectAccessible(page, "sign-in panel dark");
  await page.emulateMedia({ colorScheme: "light" });
  await themeApplied(page, "light");

  await sendStart(page, token);
  await press(page, (await lastButtons(page)).find((b) => b.startsWith("c:") && b.endsWith(`:${code}`))!);
  await expect(page).not.toHaveURL(/ingresar/, { timeout: 10_000 });
});

test("a wrong code is refused", async ({ page }) => {
  test.slow();
  await configureBot(page);
  await linkOwnTelegram(page);
  const { code, token } = await startTelegramSignIn(page);

  await sendStart(page, token);
  await press(page, (await lastButtons(page)).find((b) => b.startsWith("c:") && !b.endsWith(`:${code}`))!);
  await expect(page.getByText("Elegiste un código distinto")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "Intentar de nuevo" })).toBeVisible();
});

test("Telegram option hidden when off", async ({ page }) => {
  await page.goto("/ingresar");
  await expect(page.getByLabel("Correo electrónico")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ingresar con Telegram" })).toHaveCount(0);
});
