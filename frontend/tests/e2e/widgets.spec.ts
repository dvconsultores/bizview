// Feature 065. A dashboard embedded in another web page: the admin's panel, the in-product test
// page, the framed document a visitor gets, and the per-widget ceiling.
//
// What only a browser can prove here: the framed document renders with no product chrome, it never
// asks who the viewer is (an admin's cookie changes nothing), the widget is content-height at every
// width, the snippet's key never reaches browser storage, and the test page shows the snippet only
// when it was reached from the creation/replacement screen. The cross-origin case — a real host
// page on another origin — is `widgets-cross-origin.spec.ts`; the framing policy is also proved where
// it is decided: backend/tests/test_widgets.py and deploy/tests/test_caddy_widget.sh.
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { reportAction } from "./fixtures/report-action";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const SITE = "https://www.cliente.com";

const WIDGET_ENV = {
  share_links_enabled: true,
  embed_widgets_enabled: true,
  widget_rate_limit: 300,
};

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function enableWidgets(page: Page, extra: Record<string, unknown> = {}) {
  const response = await page.request.post("/api/test/settings", {
    headers: FETCH,
    data: { ...WIDGET_ENV, ...extra },
  });
  expect(response.ok()).toBeTruthy();
}

async function createWidget(page: Page, sites: string[] = [SITE], extra: Record<string, unknown> = {}) {
  const response = await page.request.post("/api/dashboards/ventas/widgets", {
    headers: FETCH,
    data: { name: "Ventas · cliente", sites, ...extra },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { id: number; key: string; url: string; snippet: string };
}

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
}

test.beforeEach(async ({ page }) => {
  await enableWidgets(page);
});

test.afterEach(async ({ page }) => {
  await page.request.post("/api/test/settings/reset", { headers: FETCH });
});

test("an admin creates a widget, copies its snippet and sees the warning", async ({ page }) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await reportAction(page, "Insertar en un sitio web");

  const panel = page.getByRole("region", { name: "Insertar en un sitio web" });
  await expect(panel).toBeVisible();
  // FR-012: in plain words, before anything is created and in the list.
  await expect(panel.getByText(/Los filtros son una comodidad para el visitante/)).toBeVisible();
  await expect(panel.getByText(/verá todos los datos de este tablero/)).toBeVisible();

  await panel.getByLabel("Nombre del widget").fill("Ventas · cliente");
  await panel.getByLabel("Sitios permitidos").fill(`${SITE}\nhttp://localhost:5173`);
  await panel.getByRole("button", { name: "Crear widget" }).click();

  // FR-002: the snippet is shown once, ready to copy.
  await expect(panel.getByText("Copia el fragmento ahora: no se volverá a mostrar.")).toBeVisible();
  const snippet = (await panel.locator("pre").first().textContent()) ?? "";
  expect(snippet).toContain("<iframe");
  expect(snippet).toMatch(/\/w\/[A-Za-z0-9_-]{20,}/);
  expect(await panel.getByRole("button", { name: /Copiar/ }).count()).toBeGreaterThan(0);

  // FR-021: the list shows the name, the sites (the local one marked), the creator and the state.
  const item = panel.locator("ul > li").filter({ hasText: "Ventas · cliente" });
  await expect(item).toBeVisible();
  await expect(item.getByText(SITE)).toBeVisible();
  await expect(item.getByText("Desarrollo")).toBeVisible();
  await expect(item).toContainText("Activo");
  await expect(item).toContainText("Creado por Superusuario");
  await expect(item.getByText(/\d+ vista\(s\)/)).toBeVisible();

  await expectNoHorizontalScroll(page);
});

test("the snippet is held in memory, never in browser storage, and shown once", async ({ page }) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await reportAction(page, "Insertar en un sitio web");
  const panel = page.getByRole("region", { name: "Insertar en un sitio web" });
  await expect(panel).toBeVisible();

  await panel.getByLabel("Nombre del widget").fill("Con fragmento");
  await panel.getByLabel("Sitios permitidos").fill(SITE);
  await panel.getByRole("button", { name: "Crear widget" }).click();
  const snippet = (await panel.locator("pre").first().textContent()) ?? "";
  const key = snippet.match(/\/w\/([A-Za-z0-9_-]{20,})/)?.[1] ?? "";
  expect(key).not.toBe("");

  // Defect 5: the key is in memory only — no sessionStorage, no localStorage, no cookie.
  const stored = await page.evaluate(() => ({
    session: Object.entries(sessionStorage),
    local: Object.entries(localStorage),
  }));
  expect(JSON.stringify(stored)).not.toContain(key);
  const cookies = await page.context().cookies();
  expect(cookies.some((cookie) => cookie.value.includes(key))).toBe(false);

  // Reached from the creation screen: the test page shows the snippet once…
  // The created block is above the list, which also has a Probar link per widget.
  await panel.getByRole("link", { name: "Probar" }).first().click();
  await expect(page.getByRole("heading", { name: /Probar «Con fragmento»/ })).toBeVisible();
  await expect(page.locator("pre")).toContainText("/w/");
  await expect(page.locator("pre")).toContainText(key);

  // …and a reload loses it: it is not stored anywhere, so the page explains it was shown once.
  await page.reload();
  await expect(page.getByRole("heading", { name: /Probar «Con fragmento»/ })).toBeVisible();
  await expect(page.locator("pre")).toHaveCount(0);
  await expect(page.getByText(/no se guarda en el navegador|se muestra una sola vez/i)).toBeVisible();
  // The preview still frames the widget, so the snippet's absence does not block testing.
  await expect(page.frameLocator("iframe").getByRole("region", { name: "Indicadores" }))
    .toBeVisible();
});

test("the test page frames the widget at three widths and never reads the session", async ({
  page,
  browser,
}, testInfo) => {
  await signIn(page);
  const widget = await createWidget(page, [SITE, "http://localhost:5173"]);

  await page.goto(`/d/ventas/widgets/${widget.id}/probar`);
  const frame = page.locator("iframe");
  await expect(frame).toBeVisible();

  // The framed document is the widget: the dashboard renders, the product's chrome does not.
  const inner = page.frameLocator("iframe");
  await expect(inner.getByRole("heading", { level: 1, name: "Ventas", exact: true })).toBeVisible();
  await expect(inner.getByRole("navigation")).toHaveCount(0);
  await expect(inner.getByRole("link", { name: /Tableros|Inicio|Perfil|Ayuda/ })).toHaveCount(0);
  await expect(inner.getByRole("button", { name: "Cerrar sesión" })).toHaveCount(0);
  // FR-023: the installation's legal pages stay reachable.
  await expect(inner.getByRole("link", { name: "Privacidad" })).toHaveAttribute(
    "href",
    "https://www.getbizview.com/privacidad/",
  );
  await expect(inner.getByRole("region", { name: "Indicadores" })).toBeVisible();

  // FR-018: phone, tablet and desktop widths, each one re-flowed; FR-025: no inner scrollbar.
  for (const [width, min] of [["Teléfono", 300], ["Tableta", 700], ["Escritorio", 900]] as const) {
    await page.getByRole("radio", { name: width }).click();
    const box = await frame.boundingBox();
    expect(box).not.toBeNull();
    if (width !== "Escritorio") {
      expect(Math.round(box!.width)).toBeLessThanOrEqual(min + 80);
    }
    await expect
      .poll(async () => frame.evaluate((el) => Math.round((el as HTMLElement).getBoundingClientRect().height)))
      .toBeGreaterThan(160);
  }

  // FR-019: the preview does not count as a visit.
  const listing = await page.request.get("/api/dashboards/ventas/widgets");
  const listed = ((await listing.json()) as { items: { id: number; visits: number }[] }).items.find(
    (item) => item.id === widget.id,
  );
  expect(listed?.visits).toBe(0);

  // FR-010 in the browser: the same document with an admin's cookie and without it. The widget
  // page never calls /api/me, and the payloads are identical.
  const cookies = await page.context().cookies();
  const contextOptions = {
    baseURL: testInfo.project.use.baseURL as string,
    locale: testInfo.project.use.locale as string,
  };
  const signedIn = await browser.newContext(contextOptions);
  await signedIn.addCookies(cookies);
  const signedPage = await signedIn.newPage();
  const sessionCalls: string[] = [];
  signedPage.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/")) sessionCalls.push(path);
  });
  try {
    await signedPage.goto(`/w/${widget.key}`);
    await expect(
      signedPage.getByRole("heading", { level: 1, name: "Ventas", exact: true }),
    ).toBeVisible();
    expect(sessionCalls).not.toContain("/api/me");
    expect(sessionCalls.some((path) => path.startsWith("/api/widgets/"))).toBe(true);

    const anonymousContext = await browser.newContext(contextOptions);
    try {
      const anonymousPage = await anonymousContext.newPage();
      await anonymousPage.goto(`/w/${widget.key}`);
      await expect(
        anonymousPage.getByRole("heading", { level: 1, name: "Ventas", exact: true }),
      ).toBeVisible();
      const anonData = await anonymousPage.request.get(`/api/widgets/${widget.key}/data?${SELECTION}`);
      const signedData = await signedIn.request.get(`/api/widgets/${widget.key}/data?${SELECTION}`);
      expect(signedData.status()).toBe(200);
      expect(await signedData.json()).toEqual(await anonData.json());
    } finally {
      await anonymousContext.close();
    }

    // FR-014: nothing about the widget is indexed or cached. The document headers come from the
    // edge and are asserted in deploy/tests/test_caddy_widget.sh; here the API's are.
    const api = await signedPage.request.get(`/api/widgets/${widget.key}`);
    expect(api.headers()["x-robots-tag"]).toBe("noindex, nofollow");
    expect(api.headers()["cache-control"]).toBe("no-store");
  } finally {
    await signedIn.close();
  }
});

test("a visitor without an account sees the dashboard until the widget is revoked", async ({
  page,
  browser,
}, testInfo) => {
  await signIn(page);
  const widget = await createWidget(page);

  const visitor: BrowserContext = await browser.newContext({
    baseURL: testInfo.project.use.baseURL as string,
    locale: testInfo.project.use.locale as string,
  });
  try {
    const view = await visitor.newPage();
    // The dashboard's default period is the current month; the fixture's rows are dated, so the
    // page is opened on the same period the rest of the e2e suite uses.
    await view.goto(`/w/${widget.key}?${SELECTION}`);
    await expect(view.getByRole("heading", { level: 1, name: "Ventas", exact: true })).toBeVisible();
    await expect(view.getByRole("region", { name: "Indicadores" })).toContainText(/11,75\sUSD/);

    // The visitor holds no session at all.
    expect((await visitor.request.get("/api/me")).status()).toBe(401);

    // FR-013/US3: a revoked widget shows one neutral message and no data.
    const revoked = await page.request.delete(`/api/dashboards/ventas/widgets/${widget.id}`, {
      headers: FETCH,
    });
    expect(revoked.status()).toBe(204);

    await view.reload();
    await expect(view.getByRole("heading", { name: "Contenido no disponible" })).toBeVisible();
    await expect(view.getByText("Este contenido no está disponible.")).toBeVisible();
    await expect(view.getByRole("region", { name: "Indicadores" })).toHaveCount(0);
    await expect(view.getByText(/11,75/)).toHaveCount(0);
    await expectNoHorizontalScroll(view);
  } finally {
    await visitor.close();
  }
});

test("the per-widget ceiling shows a retry inside the host page", async ({ page }) => {
  await signIn(page);
  await enableWidgets(page, { widget_rate_limit: 2 });
  const widget = await createWidget(page, [SITE], { name: "Con techo" });

  const base = `/api/widgets/${widget.key}`;
  expect((await page.request.get(base)).status()).toBe(200);
  expect((await page.request.get(`${base}/data?${SELECTION}`)).status()).toBe(200);
  const limited = await page.request.get(base);
  expect(limited.status()).toBe(429);
  expect((await limited.json()).error.code).toBe("rate_limited");

  // FR-015: the visitor is told to try again; the host page is unaffected.
  await page.goto(`/w/${widget.key}`);
  await expect(page.getByRole("heading", { name: "Un momento" })).toBeVisible();
  await expect(page.getByText(/Inténtalo de nuevo/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Reintentar" })).toBeVisible();
});
