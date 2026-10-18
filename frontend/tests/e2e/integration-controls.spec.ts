import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

// Feature 013 — integration controls (specs/013-integration-controls). The seeded integration
// "ventas-prueba" runs "*/30 * * * *" per its spec; every test puts its control back to the spec
// defaults for the projects and suites that run after it. Stop is covered by backend tests.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function reauthWith(page: Page, password: string) {
  const res = await page.request.post("/api/auth/reauth", { headers: FETCH, data: { password } });
  expect(res.status()).toBe(204);
}

async function expectAccessible(page: Page, where: string) {
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function expectView(page: Page, title: string) {
  const view = page.locator("main").getByRole("region", { name: title, exact: true });
  await expect(view).toBeVisible();
  await expect(page.locator("[role=dialog], [aria-modal]")).toHaveCount(0);
  await expect(page.locator("main > div").first()).toBeHidden();
  return view;
}

function card(page: Page) {
  return page
    .locator("main li")
    .filter({ has: page.getByRole("heading", { name: "ventas-prueba", exact: true }) })
    .first();
}

function fact(page: Page, label: string) {
  return card(page)
    .locator("dl > div")
    .filter({ has: page.locator("dt", { hasText: new RegExp(`^${label}$`) }) })
    .locator("dd");
}

async function resetControl(browser: Browser) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page);
  await reauthWith(page, SUPER.password);
  const res = await page.request.put("/api/integrations/ventas-prueba/control", {
    headers: FETCH,
    data: {
      paused: false,
      schedule: null,
      full_rebuild_cron: null,
      window_start: null,
      window_end: null,
    },
  });
  expect(res.status()).toBe(200);
  await ctx.close();
}

async function waitForControlPut(page: Page) {
  return page.waitForResponse(
    (r) =>
      r.request().method() === "PUT" &&
      new URL(r.url()).pathname === "/api/integrations/ventas-prueba/control",
    { timeout: 15_000 }
  );
}

test.describe("integration controls (feature 013)", () => {
  test.beforeAll(async ({ browser }) => {
    await resetControl(browser);
  });

  test.afterEach(async ({ browser }) => {
    await resetControl(browser);
  });

  test("pause and resume", async ({ page }) => {
    await signIn(page);
    await reauthWith(page, SUPER.password);
    await page.goto("/admin/integraciones");

    const c = card(page);
    await expect(c.getByText("Activa", { exact: true })).toBeVisible();
    await expect(fact(page, "Frecuencia")).toHaveText(/Cada 30 minutos\s*\(spec\)/);
    await expect(fact(page, "Horario permitido")).toHaveText("Todo el día");
    await expect(fact(page, "Recarga completa")).toContainText("Diaria a las 03:00");
    await expect(c.getByRole("button", { name: "Detener" })).toHaveCount(0);
    await expect(fact(page, "Próxima ejecución")).not.toHaveText("—");

    const putPause = waitForControlPut(page);
    await c.getByRole("button", { name: "Pausar" }).click();
    const resPause = await putPause;
    expect(resPause.ok()).toBeTruthy();

    await expect(c.getByText("Pausada", { exact: true })).toBeVisible();
    await expect(fact(page, "Próxima ejecución")).toHaveText("—");
    await expect(c.getByRole("button", { name: "Reanudar" })).toBeVisible();
    await expectAccessible(page, "paused");

    await page.reload();
    await expect(card(page).getByText("Pausada", { exact: true })).toBeVisible();
    await expect(fact(page, "Próxima ejecución")).toHaveText("—");

    const putResume = waitForControlPut(page);
    await card(page).getByRole("button", { name: "Reanudar" }).click();
    const resResume = await putResume;
    expect(resResume.ok()).toBeTruthy();

    await expect(card(page).getByText("Activa", { exact: true })).toBeVisible();
    await expect(fact(page, "Próxima ejecución")).not.toHaveText("—");
  });

  test("change frequency, window, invalid custom, restore spec", async ({ page }) => {
    await signIn(page);
    await reauthWith(page, SUPER.password);
    await page.goto("/admin/integraciones");

    const c = card(page);
    await c.getByRole("button", { name: "Cambiar frecuencia" }).click();
    let view = await expectView(page, "Frecuencia de ventas-prueba");
    await expect(view.getByRole("radio", { name: "Cada 30 minutos" })).toBeChecked();
    await expectAccessible(page, "frequency view");

    await view.getByRole("radio", { name: "Cada 15 minutos" }).check();
    await view.getByRole("checkbox", { name: "Limitar las horas en que puede empezar" }).check();
    await view.getByLabel("Desde").fill("06:00");
    await view.getByLabel("Hasta").fill("22:00");

    const putSave = waitForControlPut(page);
    await view.getByRole("button", { name: "Guardar" }).click();
    const resSave = await putSave;
    expect(resSave.ok()).toBeTruthy();

    await expect(view).toBeHidden();
    await expect(fact(page, "Frecuencia")).toHaveText(/Cada 15 minutos\s*\(personalizada\)/);
    await expect(fact(page, "Horario permitido")).toHaveText("06:00–22:00");

    await c.getByRole("button", { name: "Cambiar frecuencia" }).click();
    view = await expectView(page, "Frecuencia de ventas-prueba");
    await expect(view.getByRole("radio", { name: "Cada 15 minutos" })).toBeChecked();
    await expect(
      view.getByRole("checkbox", { name: "Limitar las horas en que puede empezar" })
    ).toBeChecked();

    await view.getByRole("radio", { name: "Personalizada" }).check();
    await view.getByLabel("Expresión cron", { exact: true }).fill("*/1 * * * *");
    const putTooFrequent = waitForControlPut(page);
    await view.getByRole("button", { name: "Guardar" }).click();
    const resTooFrequent = await putTooFrequent;
    expect(resTooFrequent.status()).toBe(422);
    await expect(view).toBeVisible();
    await expect(
      view.getByText("La frecuencia mínima es una vez cada 5 minutos.")
    ).toBeVisible();

    await view.getByLabel("Expresión cron", { exact: true }).fill("no es cron");
    const putInvalid = waitForControlPut(page);
    await view.getByRole("button", { name: "Guardar" }).click();
    const resInvalid = await putInvalid;
    expect(resInvalid.status()).toBe(422);
    await expect(view).toBeVisible();
    await expect(
      view.getByText("La expresión no es válida. Usa 5 campos: minuto hora día mes día-de-semana.")
    ).toBeVisible();
    await expectAccessible(page, "frequency errors");

    await view.getByRole("button", { name: "Cancelar" }).click();
    await expect(view).toBeHidden();
    await expect(fact(page, "Frecuencia")).toHaveText(/Cada 15 minutos\s*\(personalizada\)/);

    await c.getByRole("button", { name: "Cambiar frecuencia" }).click();
    view = await expectView(page, "Frecuencia de ventas-prueba");
    const putRestore = waitForControlPut(page);
    await view.getByRole("button", { name: "Usar la programación del spec" }).click();
    const resRestore = await putRestore;
    expect(resRestore.ok()).toBeTruthy();

    await expect(view).toBeHidden();
    await expect(fact(page, "Frecuencia")).toHaveText(/Cada 30 minutos\s*\(spec\)/);
    await expect(fact(page, "Horario permitido")).toHaveText("06:00–22:00");

    await c.getByRole("button", { name: "Cambiar frecuencia" }).click();
    view = await expectView(page, "Frecuencia de ventas-prueba");
    await view.getByRole("checkbox", { name: "Limitar las horas en que puede empezar" }).uncheck();
    const putWindowOff = waitForControlPut(page);
    await view.getByRole("button", { name: "Guardar" }).click();
    const resWindowOff = await putWindowOff;
    expect(resWindowOff.ok()).toBeTruthy();

    await expect(view).toBeHidden();
    await expect(fact(page, "Horario permitido")).toHaveText("Todo el día");

    expect(
      await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    ).toBeLessThanOrEqual(0);

    const apiRes = await page.request.get("/api/integrations", { headers: FETCH });
    expect(apiRes.ok()).toBeTruthy();
    const apiBody = (await apiRes.json()) as {
      items: { id: string; control: { schedule_source: string; window: unknown } }[];
    };
    const item = apiBody.items.find((i) => i.id === "ventas-prueba");
    expect(item).toBeDefined();
    expect(item!.control.schedule_source).toBe("spec");
    expect(item!.control.window).toBeNull();
  });
});
