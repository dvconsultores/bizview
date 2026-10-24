import { expect, test, type Page } from "@playwright/test";
import { reportAction } from "./fixtures/report-action";

// Route handlers may still be fetching when a test ends; drop them so no request outlives it.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

// Feature 015 — dashboard auto-refresh and TV mode (specs/015-dashboard-autorefresh/spec.md).
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION =
  "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

// Advance the fake clock one check at a time until `count()` reaches `target`.
// The next timer is only scheduled after the previous request settles, so we
// only fast-forward while the count is below target, and retry when no timer was pending.
async function advanceUntil(page: Page, count: () => number, target: number) {
  await expect
    .poll(
      async () => {
        if (count() < target) await page.clock.fastForward(61_000);
        return count();
      },
      { intervals: [250], timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(target);
}

const kpi = (page: Page, label: string) =>
  page
    .getByRole("region", { name: "Indicadores" })
    .getByRole("listitem")
    .filter({ hasText: label });

const sheet = (page: Page) => page.getByTestId("report-sheet");

/** Feature 030: the period and the auto-refresh controls live in the sheet's Parámetros tab. */
async function params(page: Page) {
  if ((await sheet(page).count()) === 0) await reportAction(page, "Parámetros");
  await expect(sheet(page)).toBeVisible();
  await expect(sheet(page).getByRole("tab", { name: "Parámetros" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  return sheet(page);
}

async function expectNoHorizontalScroll(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      ),
    )
    .toBeLessThanOrEqual(0);
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("data mode: no bump => only version checks; bump => one refresh and draft kept", async (
    { page },
    testInfo,
  ) => {
    test.skip(
      testInfo.project.name.endsWith("-320"),
      "desktop layout checked once per engine",
    );

    await page.clock.install();
    await signIn(page);

    let versionCalls = 0;
    let versionStarted = 0;
    let dataCalls = 0;
    page.on("request", (req) => {
      const path = new URL(req.url()).pathname;
      if (path === "/api/reports/ventas/version") versionStarted++;
    });
    page.on("requestfinished", (req) => {
      const path = new URL(req.url()).pathname;
      if (path === "/api/reports/ventas/version") versionCalls++;
      if (path === "/api/reports/ventas/data") dataCalls++;
    });

    let bumped = false;
    await page.route("**/api/reports/ventas/version", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({
        response,
        json: bumped
          ? { ...body, data_version: "e2e-bumped" }
          : body,
      });
    });
    await page.route("**/api/reports/ventas/data?**", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({
        response,
        json: bumped
          ? {
              ...body,
              freshness: {
                ...body.freshness,
                data_version: "e2e-bumped",
              },
            }
          : body,
      });
    });

    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    // Feature 030: the period applies live in the sheet; there is no pending state to keep.
    const panel = await params(page);
    await panel.getByLabel("Frecuencia").selectOption("data");
    await expect(page.getByTestId("autorefresh-status")).toContainText(
      "Actualización automática · última",
    );

    // Ignore the initial requests; count only auto-refresh work from now on.
    versionCalls = 0;
    versionStarted = 0;
    dataCalls = 0;

    // No data bump: three checks => /version >= 3, /data 0 (SC-002).
    await advanceUntil(page, () => versionCalls, 3);
    expect(dataCalls).toBe(0);

    // Bump the version only after no /version request is in flight.
    await expect.poll(() => versionCalls).toBe(versionStarted);
    bumped = true;
    await advanceUntil(page, () => dataCalls, 1);

    await expect(page.getByText(/Datos actualizados \d{2}:\d{2}/)).toBeVisible();

    // The applied selection is untouched by the refresh and the sheet stays open.
    await expect(panel.getByLabel("Desde")).toHaveValue("2026-09-27");
    await expect(page).toHaveURL(/from=2026-09-27/);

    // No further refresh: the version on screen is now the bumped one.
    const v = versionCalls;
    await advanceUntil(page, () => versionCalls, v + 1);
    await page.waitForTimeout(500);
    expect(dataCalls).toBe(1);

    // The setting is remembered after reload.
    await page.reload();
    await expect((await params(page)).getByLabel("Frecuencia")).toHaveValue("data");
    await expect
      .poll(() =>
        page.evaluate(() =>
          localStorage.getItem("bizview.autorefresh.ventas"),
        ),
      )
      .toBe("data");
  });

  test("interval mode refreshes on schedule, off stops it", async (
    { page },
    testInfo,
  ) => {
    test.skip(
      testInfo.project.name.endsWith("-320"),
      "desktop layout checked once per engine",
    );

    await page.clock.install();
    await signIn(page);

    let versionCalls = 0;
    let dataCalls = 0;
    page.on("requestfinished", (req) => {
      const path = new URL(req.url()).pathname;
      if (path === "/api/reports/ventas/version") versionCalls++;
      if (path === "/api/reports/ventas/data") dataCalls++;
    });

    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    const panel = await params(page);
    await panel.getByLabel("Frecuencia").selectOption("1");

    // Ignore the initial requests.
    versionCalls = 0;
    dataCalls = 0;

    await advanceUntil(page, () => dataCalls, 1);
    expect(versionCalls).toBe(0);

    await advanceUntil(page, () => dataCalls, 2);
    expect(versionCalls).toBe(0);

    await panel.getByLabel("Frecuencia").selectOption("off");
    await page.clock.fastForward(61_000);
    await page.waitForTimeout(500);
    expect(dataCalls).toBe(2);
    expect(versionCalls).toBe(0);
    await expect(page.getByTestId("autorefresh-status")).toHaveCount(0);
  });
});

test.describe("tv desktop", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test("TV mode: full chrome hidden, large figures, Esc and exit keep parameters", async (
    { page },
    testInfo,
  ) => {
    test.skip(
      testInfo.project.name.endsWith("-320"),
      "desktop layout checked once per engine",
    );

    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    await reportAction(page, "Modo TV");
    await expect(page).toHaveURL(/tv=1/);

    const tvLayout = page.getByTestId("tv-layout");
    await expect(tvLayout).toBeVisible();
    await expect(tvLayout.getByRole("heading", { level: 1 })).toHaveText(/\S/);
    await expect(
      page.getByRole("navigation", { name: "Principal" }),
    ).toHaveCount(0);
    await expect(page.getByRole("contentinfo")).toHaveCount(0);
    await expect(sheet(page)).toHaveCount(0);

    // Wait for the report data, then check the TV value size (SC-003).
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    const size = await page
      .getByTestId("tv-layout")
      .getByRole("region", { name: "Indicadores" })
      .locator("li span.tabular-nums")
      .first()
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(size).toBeGreaterThanOrEqual(48);

    // Auto-refresh is on, but not persisted.
    await expect(page.getByTestId("autorefresh-status")).toContainText(
      "Actualización automática · última",
    );
    expect(
      await page.evaluate(() =>
        localStorage.getItem("bizview.autorefresh.ventas"),
      ),
    ).toBeNull();

    // Exit via the button keeps other parameters.
    await page.getByRole("button", { name: "Salir del modo TV" }).click();
    await expect(page).not.toHaveURL(/tv=1/);
    await expect(page).toHaveURL(/from=2026-09-27/);
    await expect(page).toHaveURL(/compare=previous_period/);
    await expect(page.getByRole("button", { name: "Parámetros", exact: true })).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "Principal" }).first(),
    ).toBeVisible();

    // Esc also exits.
    await reportAction(page, "Modo TV");
    await expect(page.getByTestId("tv-layout")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("tv-layout")).toHaveCount(0);
    await expect(page).not.toHaveURL(/tv=1/);
  });
});

test("offline: status shows reconnecting and data stays on screen", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
  // Fake clock only after the report loaded: installed earlier it freezes the page's own startup.
  await page.clock.install();

  // Feature 030: the sheet is the same at every width.
  await (await params(page)).getByLabel("Frecuencia").selectOption("data");
  await page.keyboard.press("Escape");
  await expect(sheet(page)).toHaveCount(0);

  await page.route("**/api/reports/ventas/version", (route) =>
    route.abort("internetdisconnected"),
  );
  await page.clock.fastForward(61_000);

  await expect(page.getByTestId("autorefresh-status")).toContainText(
    "Sin conexión — reintentando",
  );
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

  await page.unroute("**/api/reports/ventas/version");
  await page.clock.fastForward(6_000);

  await expect(page.getByTestId("autorefresh-status")).toContainText(
    "Actualización automática · última",
  );
});

test("TV mode via link opens directly and is mobile-safe", async ({ page }) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}&tv=1`);

  const tvLayout = page.getByTestId("tv-layout");
  await expect(tvLayout).toBeVisible();
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
  await expectNoHorizontalScroll(page);

  const exitButton = page.getByRole("button", { name: "Salir del modo TV" });
  await expect(exitButton).toBeVisible();
  const box = await exitButton.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height).toBeGreaterThanOrEqual(44);
});

test("TV mode link requires sign-in", async ({ page }) => {
  await page.goto(`/r/ventas?${SELECTION}&tv=1`);
  await expect(page).toHaveURL(/\/ingresar/);
});
