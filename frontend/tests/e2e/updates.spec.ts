// Feature 025 US2 — "a new version is available": the notice reads the entry document the server
// serves now, so simulating a deployment (another hashed bundle in index.html) is enough to see it.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

/** A deployment is a new `index.html`: same document, another hashed entry asset. */
async function deployAnotherBundle(page: Page, entry: string) {
  await page.route("**/index.html", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: `<!doctype html><html lang="es"><head><script type="module" crossorigin src="${entry}"></script></head><body><div id="root"></div></body></html>`,
    }));
}

/** The check runs on the interval and the moment the tab becomes visible again (a wall screen). */
async function backToTheTab(page: Page) {
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
}

test("a new build shows the notice; the running one never does", async ({ page }, info) => {
  test.setTimeout(240_000);
  test.skip(info.project.name.endsWith("-320"), "the notice is checked once per engine");
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);

  // The bundle the page is running is the deployed one: nothing is announced.
  const notice = page.getByText("Hay una versión nueva de la aplicación. Recarga para usarla.");
  await expect(notice).toHaveCount(0);

  await deployAnotherBundle(page, "/assets/index-after-update.js");
  await backToTheTab(page);
  await expect(notice).toBeVisible();
  await expect(page.getByRole("button", { name: "Recargar", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.querySelector('[role="dialog"]') !== null)).toBe(false);

  // The notice is dismissible and does not come back for this tab.
  await page.getByRole("button", { name: "Ahora no", exact: true }).click();
  await expect(notice).toHaveCount(0);
  await backToTheTab(page);
  await expect(notice).toHaveCount(0);

  // A reload picks up the deployed document: the notice is about the build, not about the tab.
  await page.unroute("**/index.html");
  await page.reload();
  await backToTheTab(page);
  await expect(notice).toHaveCount(0);

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
});
