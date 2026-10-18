// Feature 018. Dashboard sharing: expiring share links + send dashboard by email.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";

type Mail = {
  to: string;
  from: string;
  subject: string;
  text: string;
  attachments: { filename: string | null; content_type: string; size: number; sha256: string }[];
  link: string | null;
};

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function check(page: Page) {
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
  // axe measures target obscuring at the current scroll position; anchor to the top
  // so sticky bars from a prior click at the bottom do not cause false positives.
  await page.evaluate(() => window.scrollTo(0, 0));
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

const kpi = (page: Page, label: string) =>
  page.getByRole("region", { name: "Indicadores" }).getByRole("listitem").filter({ hasText: label });

// The installation environment these tests need (SMTP_* and SHARE_LINKS_ENABLED in .env);
// the fake SMTP server of the e2e backend listens as smtp.prueba.local:2525.
const MAIL_ENV = {
  smtp_host: "smtp.prueba.local",
  smtp_port: 2525,
  smtp_security: "none",
  smtp_user: null,
  smtp_password: null,
  smtp_from: "bizview@prueba.local",
  smtp_from_name: "Bizview",
  email_allowed_domains: "cliente.com",
  share_links_enabled: true,
};

test.beforeEach(async ({ request }) => {
  await request.post("/api/test/mail/reset", { headers: FETCH });
  const configure = await request.post("/api/test/settings", {
    headers: FETCH,
    data: MAIL_ENV,
  });
  expect(configure.ok()).toBeTruthy();
  const status = (await configure.json()).status;
  expect(status.enabled).toBe(true);
  expect(status.sharing_enabled).toBe(true);
  expect(status.allowed_domains).toEqual(["cliente.com"]);
});

test.afterEach(async ({ request }) => {
  await request.post("/api/test/mail/reset", { headers: FETCH });
  await request.post("/api/test/settings/reset", { headers: FETCH });
});

test(
  "an administrator shares a dashboard link; it opens without a session, downloads the PDF and stops working when revoked",
  async ({ page, browser }, testInfo) => {
    test.slow();
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await page.getByRole("button", { name: "Compartir" }).click();
    const shareRegion = page.getByRole("region", { name: "Compartir tablero" });
    await expect(shareRegion.getByRole("heading", { name: "Compartir tablero" })).toBeVisible();

    const oneDay = shareRegion.getByRole("group", { name: "Vigencia (días)" }).getByRole("button", { name: "1 día" });
    await oneDay.click();
    await expect(oneDay).toHaveAttribute("aria-pressed", "true");

    const note = `E2E ${testInfo.project.name}`;
    await shareRegion.getByLabel("Nota (opcional)").fill(note);
    await shareRegion.getByRole("button", { name: "Crear enlace" }).click();

    await expect(shareRegion.getByText("Copia el enlace ahora: no se volverá a mostrar.")).toBeVisible();
    const url = (await shareRegion.locator("code").first().textContent())?.trim() ?? "";
    const match = url.match(/\/s\/([A-Za-z0-9_-]+)$/);
    expect(match).not.toBeNull();
    const token = match?.[1] ?? "";
    expect(token).not.toBe("");

    const sharedItem = shareRegion.locator("ul > li").filter({ hasText: note });
    await expect(sharedItem).toContainText("Activo");

    const baseURL = testInfo.project.use.baseURL as string;
    const locale = testInfo.project.use.locale as string;
    const viewport = testInfo.project.use.viewport ?? undefined;
    const publicContext = await browser.newContext({
      baseURL,
      locale,
      viewport,
      reducedMotion: "reduce",
    });
    const publicPage = await publicContext.newPage();
    try {
      const me = await publicContext.request.get("/api/me");
      expect(me.status()).toBe(401);

      const pageResponse = await publicPage.goto(`/s/${token}?${SELECTION}`);
      expect(pageResponse).not.toBeNull();
      expect(pageResponse!.headers()["x-robots-tag"]).toBe("noindex, nofollow");
      expect(pageResponse!.headers()["cache-control"]).toBe("no-store");

      const apiResponse = await publicContext.request.get(`/api/shared/${token}`);
      expect(apiResponse.status()).toBe(200);
      expect(apiResponse.headers()["x-robots-tag"]).toContain("noindex");
      expect(apiResponse.headers()["cache-control"]).toContain("no-store");

      await expect(publicPage.getByText(/Vista compartida · vence el/)).toBeVisible();
      await expect(publicPage.getByRole("heading", { level: 1, name: "Ventas", exact: true })).toBeVisible();
      await expect(kpi(publicPage, "Ventas netas")).toContainText(/11,75\sUSD/);
      await expect(publicPage.getByRole("button", { name: "Cerrar sesión" })).toHaveCount(0);
      await check(publicPage);

      const download = publicPage.waitForEvent("download");
      await publicPage.getByRole("button", { name: "Descargar PDF" }).click();
      expect((await download).suggestedFilename()).toBe("ventas-2026-09-27-2026-09-28.pdf");

      await sharedItem.getByRole("button", { name: "Revocar" }).click();
      await sharedItem.getByRole("button", { name: "Confirmar revocación" }).click();
      await expect(page.getByText("Enlace revocado.")).toBeVisible();
      await expect(sharedItem).toContainText("Revocado");
      await expect(sharedItem.getByRole("button", { name: "Revocar" })).toHaveCount(0);

      await publicPage.reload();
      await expect(
        publicPage.getByRole("heading", { level: 1, name: "Este enlace expiró o fue revocado" })
      ).toBeVisible();
      await expect(publicPage.getByRole("heading", { level: 1, name: "Ventas", exact: true })).toHaveCount(0);
    } finally {
      await publicContext.close();
    }
  }
);

test(
  "a dashboard is emailed to three recipients with the same PDF as the dashboard download",
  async ({ page }, testInfo) => {
    test.slow();
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Descargar PDF" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("ventas-2026-09-27-2026-09-28.pdf");
    const downloadedBytes = readFileSync(await download.path());
    const downloadedSha256 = createHash("sha256").update(downloadedBytes).digest("hex");

    await page.getByRole("button", { name: "Enviar por correo" }).click();
    const emailRegion = page.getByRole("region", { name: "Enviar por correo" });
    await expect(emailRegion.getByRole("heading", { name: "Enviar por correo" })).toBeVisible();

    const externalInput = emailRegion.getByLabel("Correo externo");
    await externalInput.fill("ana@otra.com");
    await emailRegion.getByRole("button", { name: "Agregar" }).click();
    await expect(emailRegion.getByText("Solo se permiten estos dominios: cliente.com")).toBeVisible();

    for (const address of ["ana@cliente.com", "luis@cliente.com"]) {
      await externalInput.fill(address);
      await emailRegion.getByRole("button", { name: "Agregar" }).click();
      await expect(emailRegion.getByRole("button", { name: `Quitar a ${address}` })).toBeVisible();
    }

    await emailRegion.getByLabel("Buscar usuarios").fill("e2e-root");
    const userResult = emailRegion.getByRole("button", { name: /e2e-root@example\.com/ }).first();
    await expect(userResult).toBeVisible();
    await userResult.click();
    await expect(emailRegion.getByRole("button", { name: /^Quitar a / })).toHaveCount(3);

    const subject = `Ventas E2E ${testInfo.project.name}`;
    await emailRegion.getByLabel("Asunto").fill(subject);
    await expect(
      emailRegion.getByRole("checkbox", { name: "Adjuntar PDF del período y filtros actuales" })
    ).toBeChecked();
    await emailRegion.getByRole("checkbox", { name: "Incluir enlace" }).check();
    await emailRegion.getByRole("button", { name: "Enviar", exact: true }).click();
    await expect(page.getByText("Envío en cola.")).toBeVisible();

    const process = await page.request.post("/api/test/mail/process", { headers: FETCH });
    expect(process.ok()).toBeTruthy();
    const processBody = await process.json();
    expect((processBody as { handled: number }).handled).toBeGreaterThanOrEqual(1);

    let messages: Mail[] = [];

    await expect
      .poll(async () => {
        await page.request.post("/api/test/mail/process", { headers: FETCH });
        const response = await page.request.get("/api/test/mail", { headers: FETCH });
        expect(response.ok()).toBeTruthy();
        messages = (await response.json()) as Mail[];
        return messages.filter((m) => m.subject === subject).length;
      })
      .toBe(3);

    const sent = messages.filter((m) => m.subject === subject);
    const rootMessage = sent.find((m) => m.to.includes("e2e-root@example.com"));
    const anaMessage = sent.find((m) => m.to.includes("ana@cliente.com"));
    const luisMessage = sent.find((m) => m.to.includes("luis@cliente.com"));
    expect(rootMessage).toBeTruthy();
    expect(anaMessage).toBeTruthy();
    expect(luisMessage).toBeTruthy();

    for (const message of [rootMessage, anaMessage, luisMessage]) {
      expect(message?.attachments.length).toBe(1);
      const pdf = message?.attachments[0];
      expect(pdf?.content_type).toBe("application/pdf");
      expect(pdf?.filename).toBe("ventas-2026-09-27-2026-09-28.pdf");
      expect(pdf?.sha256).toBe(downloadedSha256);
      expect(pdf?.size).toBe(downloadedBytes.length);
      expect(message?.link ?? "").toMatch(/\/s\/[A-Za-z0-9_-]+$/);
    }

    await emailRegion.getByRole("button", { name: "Actualizar" }).click();
    const sendItem = emailRegion.locator("li").filter({ hasText: subject }).first();
    await expect(sendItem.getByText("Enviado", { exact: true }).first()).toBeVisible();

    await check(page);
  }
);

test("an administrator schedules a weekly email on a phone, pauses it and deletes it inline", async ({ page }) => {
  test.slow();
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

  await page.getByRole("button", { name: "Envíos programados" }).click();
  const view = page.getByRole("region", { name: "Envíos programados" });
  await expect(view.getByRole("heading", { name: "Envíos programados" })).toBeVisible();
  await expect(
    view.getByText("Las horas son las de la instalación (America/Caracas).")
  ).toBeVisible();
  await expect(view.getByText("Aún no hay envíos programados.")).toBeVisible();
  await check(page);

  await view.getByRole("button", { name: "Nuevo envío programado" }).click();
  await expect(view.getByRole("heading", { name: "Nuevo envío programado" })).toBeVisible();
  const form = view.locator("form");
  await form.getByLabel("Frecuencia").selectOption("weekly");
  await form.getByLabel("Día de la semana").selectOption("2");
  await form.getByLabel("Hora", { exact: true }).selectOption("9");
  await form.getByLabel("Período a enviar").selectOption("last_7_days");
  await form.getByLabel("Correo externo").fill("ana@cliente.com");
  await form.getByRole("button", { name: "Agregar" }).click();
  await expect(form.getByRole("button", { name: "Quitar a ana@cliente.com" })).toBeVisible();
  await check(page);

  await form.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Envío programado creado.")).toBeVisible();

  const item = view.locator("li").filter({ hasText: "Cada miércoles a las 09:00" });
  await expect(item).toContainText("Últimos 7 días");
  await expect(item).toContainText("Próximo envío:");
  await expect(item).toContainText("Para: ana@cliente.com");

  let subs = await (await page.request.get("/api/dashboards/ventas/subscriptions", { headers: FETCH })).json();
  expect(subs.items).toHaveLength(1);
  expect(subs.items[0]).toMatchObject({
    frequency: "weekly",
    weekday: 2,
    hour: 9,
    paused: false,
  });
  expect(new Date(subs.items[0].next_due_at).getTime()).toBeGreaterThan(Date.now());
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Caracas",
    weekday: "short",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(subs.items[0].next_due_at));
  expect(parts.find((p) => p.type === "weekday")?.value).toBe("Wed");
  expect(parts.find((p) => p.type === "hour")?.value).toBe("09");

  await item.getByRole("button", { name: "Pausar" }).click();
  await expect(page.getByText("Envío programado actualizado.")).toBeVisible();
  await expect(item.getByText("En pausa")).toBeVisible();
  await expect(item.getByRole("button", { name: "Reanudar" })).toBeVisible();
  await expect(item.getByText("Próximo envío:")).toHaveCount(0);

  subs = await (await page.request.get("/api/dashboards/ventas/subscriptions", { headers: FETCH })).json();
  expect(subs.items[0].paused).toBe(true);
  await check(page);

  await item.getByRole("button", { name: "Eliminar" }).click();
  await expect(item.getByText("Confirmar eliminación")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await item.getByRole("button", { name: "Confirmar eliminación" }).click();
  await expect(page.getByText("Envío programado eliminado.")).toBeVisible();
  await expect(view.getByText("Aún no hay envíos programados.")).toBeVisible();

  subs = await (await page.request.get("/api/dashboards/ventas/subscriptions", { headers: FETCH })).json();
  expect(subs.items).toEqual([]);
  await check(page);
});

test("sharing and email controls are hidden when the installation turns them off", async ({ page }) => {
  const configure = await page.request.post("/api/test/settings", {
    headers: FETCH,
    data: { smtp_host: null, smtp_from: null, share_links_enabled: false },
  });
  expect(configure.ok()).toBeTruthy();
  const status = (await configure.json()).status;
  expect(status.enabled).toBe(false);
  expect(status.sharing_enabled).toBe(false);

  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await expect(page.getByRole("heading", { level: 1, name: "Ventas", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Enviar por correo" })).toHaveCount(0);
  await page.getByRole("button", { name: "Compartir" }).click();
  const shareRegion = page.getByRole("region", { name: "Compartir tablero" });
  await expect(shareRegion.getByText(/Los enlaces compartidos están desactivados/)).toBeVisible();
  await expect(shareRegion.getByRole("button", { name: "Crear enlace" })).toHaveCount(0);

  await page.goto("/s/not-a-real-token-000000000000000000000000000");
  await expect(
    page.getByRole("heading", { level: 1, name: "Este enlace expiró o fue revocado" })
  ).toBeVisible();
});

test("Administración has no email option; email settings come from the environment", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1, name: "Administración" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: /Correo/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Integraciones" })).toBeVisible();

  await page.goto("/admin/correo");
  await expect(page.getByText("404")).toBeVisible();
  await expect(page.getByLabel("Servidor (host)")).toHaveCount(0);

  const r = await page.request.get("/api/admin/mail", { headers: FETCH });
  expect(r.status()).toBe(404);

  const test = await page.request.post("/api/admin/mail/test", { headers: FETCH });
  expect(test.status()).toBe(404);

  const put = await page.request.put("/api/admin/mail", { headers: FETCH, data: {} });
  expect([404, 405]).toContain(put.status());

  await page.goto("/admin");
  await check(page);
});
