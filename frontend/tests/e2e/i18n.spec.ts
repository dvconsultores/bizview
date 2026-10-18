// Feature 022 — English / Spanish walk (specs/022-i18n-en-es). The language is stored on the super user's account, so every test resets it to NULL (follow the browser) for the suites that run after it.
import { expect, test, type Browser, type Page } from "@playwright/test";
import { es } from "../../src/i18n/es";
import { en } from "../../src/i18n/en";

const FETCH = { "X-Requested-With": "fetch" };
const SUPER_USER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const ROUTES = [
  "/",
  "/tableros",
  `/r/ventas?${SELECTION}`,
  "/d/ventas",
  "/perfil",
  "/cambiar-clave",
  "/seguridad/doble-factor",
  "/admin",
  "/admin/usuarios",
  "/admin/usuarios/nuevo",
  "/admin/auditoria",
  "/admin/ia",
  "/admin/fuentes",
  "/admin/fuentes/nueva",
  "/admin/seguridad",
  "/admin/espacio",
  "/admin/integraciones",
  "/admin/tokens",
  "/admin/asistente",
  "/no-autorizado",
  "/no-existe",
];

function leaves(node: unknown, out = new Set<string>()): Set<string> {
  if (typeof node === "string") {
    const trimmed = node.trim();
    if (trimmed) out.add(trimmed);
  } else if (Array.isArray(node)) {
    for (const item of node) leaves(item, out);
  } else if (node && typeof node === "object") {
    for (const value of Object.values(node)) leaves(value, out);
  }
  return out;
}

const ALLOW = new Set<string>([
  "Bizview", // brand
  "Español", // language names are shown in their own language on purpose
  "English", // language names are shown in their own language on purpose
  "Ventas", // report title authored in the Spanish e2e workspace
  "Ventas netas", // authored report labels of the fixture
  "Pedidos", // authored report labels of the fixture
  "Ticket promedio", // authored report labels of the fixture
  "Producto", // authored report labels of the fixture
  "Origen prueba", // fixture source name
  "Superusuario", // full name stored for the super user at creation (user data, not interface text)
]);

function onlyIn(a: Set<string>, b: Set<string>): Set<string> {
  const result = new Set<string>();
  for (const s of a) {
    const trimmed = s.trim();
    if (trimmed.length >= 4 && /[a-zA-Z]/.test(trimmed) && !b.has(trimmed) && !ALLOW.has(trimmed)) {
      result.add(trimmed);
    }
  }
  return result;
}

const SPANISH_ONLY = onlyIn(leaves(es), leaves(en));
const ENGLISH_ONLY = onlyIn(leaves(en), leaves(es));

async function expectLanguage(page: Page, lang: "es" | "en", where: string) {
  await expect(page.locator("html")).toHaveAttribute("lang", lang);
  const bodyText = await page.locator("body").innerText();
  const forbidden = lang === "en" ? SPANISH_ONLY : ENGLISH_ONLY;
  const found: string[] = [];
  for (const s of forbidden) {
    if (bodyText.includes(s)) found.push(s);
  }
  expect(found, where).toEqual([]);
}

async function signIn(page: Page, cat = es) {
  await page.goto("/ingresar");
  await page.getByLabel(cat.signIn.email, { exact: true }).fill(SUPER_USER.email);
  await page.getByLabel(cat.signIn.password, { exact: true }).fill(SUPER_USER.password);
  await page.getByRole("button", { name: cat.signIn.submit, exact: true }).click();
  await expect(page).not.toHaveURL(/\/ingresar/);
}

async function patchLocale(page: Page, locale: "en" | "es" | null) {
  const response = await page.request.patch("/api/me/preferences", {
    data: { locale },
    headers: FETCH,
  });
  expect(response.status()).toBe(200);
}

async function resetLocale(browser: Browser) {
  const context = await browser.newContext({ locale: "es-ES" });
  const page = await context.newPage();
  await signIn(page);
  await patchLocale(page, null);
  await context.close();
}

test.afterEach(async ({ browser }) => {
  await resetLocale(browser);
});

test("every screen and in-page view speaks English", async ({ page }) => {
  test.setTimeout(480_000);
  await signIn(page);
  await patchLocale(page, "en");
  await page.reload();

  // Share links and email (the e2e backend's fake SMTP server), so every sharing view exists.
  const enableRes = await page.request.post("/api/test/settings", {
    data: {
      share_links_enabled: true,
      smtp_host: "smtp.prueba.local",
      smtp_port: 2525,
      smtp_security: "none",
      smtp_from: "bizview@prueba.local",
    },
    headers: FETCH,
  });
  expect(enableRes.status()).toBe(200);
  expect((await enableRes.json()).status.enabled).toBe(true);

  try {
    for (const route of ROUTES) {
      await page.goto(route);
      await page.waitForFunction(() => document.querySelectorAll("[aria-busy=true]").length === 0);
      await expectLanguage(page, "en", route);
    }

    // In-page views on the report page
    const reportUrl = `/r/ventas?${SELECTION}`;
    await page.goto(reportUrl);
    await page.waitForFunction(() => document.querySelectorAll("[aria-busy=true]").length === 0);

    // Share view
    await page.getByRole("button", { name: en.sharing.share, exact: true }).click();
    await expect(page.getByRole("region", { name: en.sharing.shareTitle })).toBeVisible();
    await expectLanguage(page, "en", "share view");
    await page.keyboard.press("Escape");

    // Email view
    await page.getByRole("button", { name: en.sharing.email.emailButton, exact: true }).click();
    await expectLanguage(page, "en", "email view");
    await page.keyboard.press("Escape");

    // Scheduled sends view
    await page.getByRole("button", { name: en.sharing.schedules.schedulesButton, exact: true }).click();
    await expectLanguage(page, "en", "schedules view");
    await page.keyboard.press("Escape");

    // Filters view
    await page.getByRole("button", { name: en.reportParams.filtersButton(0), exact: true }).click();
    await expectLanguage(page, "en", "filters view");
    await page.keyboard.press("Escape");

    // Shared link view
    const linkRes = await page.request.post("/api/dashboards/ventas/links", {
      data: { days: 1, note: "i18n" },
      headers: FETCH,
    });
    expect(linkRes.status()).toBe(201);
    const linkData = await linkRes.json();
    await page.goto(`/s/${linkData.token}`);
    await page.waitForFunction(() => document.querySelectorAll("[aria-busy=true]").length === 0);
    await expectLanguage(page, "en", "shared view");
  } finally {
    const resetRes = await page.request.post("/api/test/settings/reset", { headers: FETCH });
    expect(resetRes.status()).toBe(200);
  }
});

test("every screen speaks Spanish", async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page);
  await patchLocale(page, "es");
  await page.reload();

  for (const route of ROUTES) {
    await page.goto(route);
    await page.waitForFunction(() => document.querySelectorAll("[aria-busy=true]").length === 0);
    await expectLanguage(page, "es", route);
  }
});

test("switching language is instant and keeps report filters", async ({ page }) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await page.waitForFunction(() => document.querySelectorAll("[aria-busy=true]").length === 0);
  const urlBefore = page.url();

  await page.getByRole("button", { name: es.nav.menu, exact: true }).click();
  const start = Date.now();
  await page.getByRole("menuitemradio", { name: es.language.en, exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(Date.now() - start).toBeLessThan(300);
  expect(page.url()).toBe(urlBefore);

  await expect.poll(async () => {
    const meRes = await page.request.get("/api/me");
    const me = await meRes.json();
    return me.locale;
  }).toBe("en");
});

test("the account language follows the user to a fresh context", async ({ page, browser }) => {
  await signIn(page);
  await patchLocale(page, "en");

  const context = await browser.newContext({ locale: "es-ES" });
  const page2 = await context.newPage();
  await signIn(page2, es);
  await expect(page2.locator("html")).toHaveAttribute("lang", "en");
  await context.close();
});

test("the sign-in page switch is saved to the account after signing in", async ({ page }) => {
  await page.goto("/ingresar");
  await page.getByRole("radio", { name: es.language.en, exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");

  await signIn(page, en);
  await expect.poll(async () => {
    const meRes = await page.request.get("/api/me");
    const me = await meRes.json();
    return me.locale;
  }).toBe("en");
});
