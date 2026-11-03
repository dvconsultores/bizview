// Feature 051 — the installation theme repaints the application, at once, and the four official
// identities are different in more than colour.
//
// The assertions are properties a reviewer would check by hand: after pressing "Usar en la
// instalación" the header band, the page background, a card and a primary button change *without a
// reload*; the choice survives a reload; a user's light/dark preference is independent of it; the
// four identities can be told apart without reading their labels; and nothing scrolls sideways on
// a phone. The screenshots are the evidence for the closure report.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SHOTS = "../docs/assets/theme-application";

const OFFICIAL = ["clasico", "impacto", "elegante", "contraste"] as const;
type Official = (typeof OFFICIAL)[number];

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

/** The tokens the whole application paints with, read from the running page. */
const tokens = (page: Page, names: readonly string[]) =>
  page.evaluate((wanted) => {
    const style = getComputedStyle(document.documentElement);
    const out: Record<string, string> = {};
    for (const name of wanted) out[name] = style.getPropertyValue(`--${name}`).trim();
    out["data-palette"] = document.documentElement.dataset.palette ?? "";
    out["data-nav"] = document.documentElement.dataset.nav ?? "";
    out["band"] = style.getPropertyValue("--c-chrome").trim();
    return out;
  }, names as string[]);

const FINGERPRINT = [
  "c-canvas", "c-surface", "c-chrome", "c-accent", "radius-card", "shadow-card", "card-border",
  "heading-weight",
] as const;

/** The installation theme in force on the page, once `/api/config` has answered: the first paint
 * may still be the product default, so every read waits for this. */
const waitForTheme = (page: Page, id: Official) =>
  expect.poll(() => page.evaluate(() => document.documentElement.dataset.palette ?? ""),
    { timeout: 20_000 }).toBe(id);

/** Apply a theme from its own card and wait for the page to say it is the one in force. */
async function applyTheme(page: Page, id: Official) {
  await page.goto("/admin/apariencia");
  const card = page.locator(`[data-theme-card="${id}"]`);
  await expect(card).toBeVisible();
  if ((await card.getAttribute("data-installed")) !== "true") {
    await card.getByRole("button", { name: "Usar en la instalación" }).click();
    await expect(card).toHaveAttribute("data-installed", "true", { timeout: 15_000 });
  }
  await waitForTheme(page, id);
}

const overflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

test.describe("the theme repaints the application", () => {
  test("applies with no reload and no re-login (FR-004, FR-005)", async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    // Whatever the fixture installed, start from Clásico so the change below is visible.
    await applyTheme(page, "clasico");
    // A marker only a full document load would destroy: this is what "no reload" means.
    const before = await tokens(page, FINGERPRINT);
    await page.evaluate(() => {
      (window as unknown as { marker: number }).marker = 42;
    });

    // Click the card in place: a navigation here would destroy the marker and prove nothing.
    const card = page.locator('[data-theme-card="contraste"]');
    await card.getByRole("button", { name: "Usar en la instalación" }).click();
    await waitForTheme(page, "contraste");
    const after = await tokens(page, FINGERPRINT);

    expect(await page.evaluate(() => (window as unknown as { marker?: number }).marker)).toBe(42);
    expect(after["c-chrome"], "the header band follows the theme").not.toBe(before["c-chrome"]);
    expect(after["c-canvas"], "the page background follows the theme").not.toBe(before["c-canvas"]);
    expect(after["data-palette"]).toBe("contraste");
    expect(after["data-nav"]).toBe("outline");

    // The band the header actually paints is the theme's chrome, not the stylesheet's fallback.
    await page.goto("/perfil");
    await waitForTheme(page, "contraste");
    const band = await page.evaluate(() => {
      const shell = document.querySelector('[data-app-band="header"]');
      return shell ? getComputedStyle(shell).backgroundColor : "missing";
    });
    expect(band).toBe("rgb(23, 35, 59)");

    await applyTheme(page, "clasico");
  });

  test("keeps the choice across a reload and a new session (FR-006)", async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await applyTheme(page, "elegante");
    await page.reload();
    await waitForTheme(page, "elegante");
    const after = await tokens(page, FINGERPRINT);
    expect(after["data-nav"]).toBe("bar");
    // A fresh session resolves the same theme.
    await page.context().clearCookies();
    await signIn(page);
    await page.goto("/perfil");
    await waitForTheme(page, "elegante");
    expect((await tokens(page, FINGERPRINT))["data-palette"]).toBe("elegante");
    await applyTheme(page, "clasico");
  });

  test("keeps the user's light/dark preference independent of the theme (US3)", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 375, height: 740 });
    await signIn(page);
    await page.goto("/perfil");
    const saved = page.waitForResponse(
      (r) => r.url().includes("/api/me/preferences") && r.request().method() === "PATCH");
    await page.getByRole("radio", { name: "Oscuro" }).click();
    await saved;
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("dark");

    await applyTheme(page, "elegante");
    await page.goto("/perfil");
    await waitForTheme(page, "elegante");
    // The installation theme changed; the user's preference did not.
    expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("dark");
    expect((await tokens(page, FINGERPRINT))["data-palette"]).toBe("elegante");
    const dark = await tokens(page, ["c-surface"]);
    expect(dark["c-surface"]).toBe("30 35 44");   // Elegante's dark surface, not its light one

    // Put the fixture back: Clásico, and the appearance preference on Sistema.
    await applyTheme(page, "clasico");
    await page.goto("/perfil");
    await page.getByRole("radio", { name: "Sistema" }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("light");
  });

  test("the four identities cannot be confused, and nothing scrolls sideways", async ({ page }) => {
    test.setTimeout(420_000);
    await signIn(page);
    const prints: Record<string, Record<string, string>> = {};
    for (const id of OFFICIAL) {
      await applyTheme(page, id);
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await waitForTheme(page, id);
      prints[id] = await tokens(page, FINGERPRINT);
      for (const width of [320, 375, 768, 1440]) {
        await page.setViewportSize({ width, height: 800 });
        await expect.poll(() => overflow(page), { message: `${id} at ${width}px` })
          .toBeLessThanOrEqual(0);
      }
    }
    for (let i = 0; i < OFFICIAL.length; i++) {
      for (let j = i + 1; j < OFFICIAL.length; j++) {
        const a = prints[OFFICIAL[i]];
        const b = prints[OFFICIAL[j]];
        const differing = FINGERPRINT.filter((name) => a[name] !== b[name]);
        expect(differing.length, `${OFFICIAL[i]} vs ${OFFICIAL[j]} differ only on ${differing}`)
          .toBeGreaterThanOrEqual(4);
      }
    }
    // Contraste is the one that must be visibly bordered and flat.
    expect(prints.contraste["card-border"]).toBe("2px");
    expect(prints.contraste["data-nav"]).toBe("outline");
    await applyTheme(page, "clasico");
  });

  test("the reference screen in all eight variants (visual evidence)", async ({ page }) => {
    test.setTimeout(600_000);
    await signIn(page);
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      for (const id of OFFICIAL) {
        await applyTheme(page, id);
        for (const [label, width, height] of [["phone", 375, 740], ["desktop", 1440, 900]] as const) {
          await page.setViewportSize({ width, height });
          await page.goto("/");
          await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
          // The first paint is the cached theme and `/api/config` reconciles it a moment later:
          // without this the screenshot could catch the previous identity.
          await waitForTheme(page, id);
          await expect.poll(() => overflow(page), { message: `${id} ${label} ${scheme}` })
            .toBeLessThanOrEqual(0);
          await page.screenshot({ path: `${SHOTS}/${id}-${label}-${scheme}.png` });
        }
        // The library itself, where the identity is chosen.
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto("/admin/apariencia");
        await expect(page.locator("[data-theme-grid]").first()).toBeVisible();
        await waitForTheme(page, id);
        await page.screenshot({ path: `${SHOTS}/apariencia-${id}-${scheme}.png` });
      }
    }
    await page.emulateMedia({ colorScheme: "light" });
    await applyTheme(page, "clasico");
  });

  test("the appearance screen stays accessible in every identity", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);
    for (const id of OFFICIAL) {
      await applyTheme(page, id);
      await page.goto("/admin/apariencia");
      await expect(page.locator("[data-theme-grid]").first()).toBeVisible();
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
      const bad = results.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${id} ${v.id}: ${v.nodes.map((n) =>
        `${n.target.join(" ")} ${JSON.stringify(n.any.map((a) => a.data))}`).join(" | ")}`))
        .toEqual([]);
    }
    await applyTheme(page, "clasico");
  });
});
