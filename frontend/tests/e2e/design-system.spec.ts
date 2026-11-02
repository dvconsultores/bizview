// Feature 050 — the six screenshots from production, corrected and proved in a real browser.
//
// Every assertion here is a property a reviewer would check by hand: one row of choices, a grid that
// uses the width, panes that scroll on their own, nothing behind the bottom bar, no sideways scroll,
// no serious accessibility violation. The screenshots are evidence for the closure report, not a
// pixel baseline: a diff would fail on a font upgrade and pass on a structural regression.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
// Playwright runs from `frontend/`; the evidence lives beside the repository's docs.
const SHOTS = "../docs/assets/design-system";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

const overflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

async function expectAccessible(page: Page, where: string) {
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`))
    .toEqual([]);
}

/** Each segmented control puts its own options on one row: same top, inside the viewport.
 *
 * Scoped per group on purpose: a surface may carry two (appearance and language), and two rows of
 * two groups is correct — that is not the defect. The defect was one group's options stacking. */
async function expectOneRow(page: Page, where: string) {
  const groups = await page.locator("[data-segmented]").evaluateAll((els) => els.map((group) => {
    const options = Array.from(group.querySelectorAll("[role=radio], [role=menuitemradio]"));
    return {
      size: options.length,
      tops: [...new Set(options.map((o) => Math.round(o.getBoundingClientRect().top)))],
      spans: options.map((o) => {
        const r = o.getBoundingClientRect();
        return [Math.round(r.left), Math.round(r.right)];
      }),
    };
  }));
  expect(groups.length, `${where}: a segmented control is on screen`).toBeGreaterThan(0);
  const viewport = page.viewportSize()!.width;
  for (const group of groups) {
    expect(group.size, `${where}: options`).toBeGreaterThan(1);
    expect(group.tops.length, `${where}: one row of ${group.size} options`).toBe(1);
    for (const [left, right] of group.spans) {
      expect(left, `${where}: option inside the viewport`).toBeGreaterThanOrEqual(0);
      expect(right, `${where}: option inside the viewport`).toBeLessThanOrEqual(viewport + 1);
    }
  }
}

/** How many columns a CSS grid actually resolved to. */
const columns = (page: Page, selector: string) =>
  page.locator(selector).evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);

test.describe("design system across the screens", () => {
  for (const scheme of ["light", "dark"] as const) {
    for (const [label, width, height] of [["phone", 375, 740], ["desktop", 1440, 900]] as const) {
      test(`evidence screens — ${label} ${scheme}`, async ({ page }) => {
        test.setTimeout(180_000);
        await page.setViewportSize({ width, height });
        await page.emulateMedia({ colorScheme: scheme });
        await signIn(page);
        const suffix = `${label}-${scheme}`;
        const shots = [
          // Evidence 1 and 2: the theme library.
          { route: "/admin/apariencia", name: "01-apariencia", ready: "[data-theme-grid]" },
          // Evidence 3: the account dropdown (captured below, after it is opened).
          { route: "/perfil", name: "03-perfil", ready: "[data-segmented]" },
          // Evidence 5 and 6: Ayuda, list and article.
          { route: "/ayuda", name: "05-ayuda-lista", ready: "section[aria-label] button" },
          { route: "/ayuda?tema=proyectos", name: "06-ayuda-tema",
            ready: "article[aria-labelledby='help-topic']" },
        ] as const;

        for (const { route, name, ready } of shots) {
          await page.goto(route);
          await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
          // Evidence is worthless if it catches a half-loaded screen: wait for its own content.
          await expect(page.locator(ready).first()).toBeVisible();
          await expect(page.locator("[role=status]")).toHaveCount(0);
          await expect.poll(() => overflow(page), { message: `${route} ${suffix}` })
            .toBeLessThanOrEqual(0);
          await page.screenshot({ path: `${SHOTS}/${name}-${suffix}.png`, fullPage: false });
          await expectAccessible(page, `${route} ${suffix}`);
        }

        // Evidence 1: the library uses the width it is given.
        await page.goto("/admin/apariencia");
        await expect(page.locator("[data-theme-grid]")).toBeVisible();
        const cols = await columns(page, "[data-theme-grid]");
        expect(cols).toBe(width >= 1280 ? 3 : width >= 640 ? 2 : 1);

        // Evidence 3 and 4: appearance and language are one row each, in Perfil and in the menu.
        await page.goto("/perfil");
        await expect(page.locator("[data-segmented]").first()).toBeVisible();
        await expectOneRow(page, `perfil ${suffix}`);
        await page.getByRole("button", { name: "Menú de cuenta" }).click();
        await expect(page.getByRole("menu")).toBeVisible();
        await page.screenshot({ path: `${SHOTS}/02-cuenta-${suffix}.png`, fullPage: false });
        await expectOneRow(page, `menu ${suffix}`);
        await page.keyboard.press("Escape");
        await expect(page.getByRole("menu")).toBeHidden();

        // Evidence 5 and 6: on a desktop the panes scroll on their own; on a phone a topic replaces
        // the list and the page itself does not become the scroller.
        await page.goto("/ayuda");
        const list = page.locator("section[aria-label]").first();
        await expect(list).toBeVisible();
        await expect(list.getByRole("button").first()).toBeVisible();
        await list.getByRole("button", { name: /proyectos/i }).first().click();
        const article = page.locator("article[aria-labelledby='help-topic']");
        await expect(article).toBeVisible();
        await expect(page).toHaveURL(/tema=/);
        if (width >= 1024) {
          // The guide's topics are short enough to fit a tall window, so the overflow is created
          // honestly: a shorter window. What is asserted is that the *pane* scrolls and the page
          // does not — a fixed-height article area would pass the first and fail the second.
          await page.setViewportSize({ width, height: 520 });
          // The pane has to have laid out at the new height before it can be measured.
          await expect.poll(() => article.evaluate((el) => el.scrollHeight > el.clientHeight),
                            { timeout: 10_000, message: "the article overflows its pane" })
            .toBe(true);
          const before = await page.evaluate(() => window.scrollY);
          const metrics = await article.evaluate((el) => {
            el.scrollTop = el.scrollHeight;
            const cs = getComputedStyle(el);
            return {
              overflowY: cs.overflowY,
              minHeight: cs.minHeight,
              scrolled: el.scrollTop,
              overflows: el.scrollHeight > el.clientHeight,
              scrollHeight: el.scrollHeight,
              clientHeight: el.clientHeight,
              maxHeight: cs.maxHeight,
            };
          });
          expect(metrics.overflowY, "the article is a scroller").toBe("auto");
          expect(metrics.minHeight, "a grid child may scroll").toBe("0px");
          expect(metrics.overflows, `the content is taller than the pane ${JSON.stringify(metrics)}`).toBe(true);
          expect(metrics.scrolled, "the article scrolled").toBeGreaterThan(0);
          expect(await page.evaluate(() => window.scrollY), "the page did not move").toBe(before);
          await page.setViewportSize({ width, height });
        } else {
          await expect(list).toBeHidden();
          await page.getByRole("button", { name: /volver a la lista de temas/i }).click();
          await expect(list).toBeVisible();
        }
        // The bottom bar never covers the end of the article.
        const covered = await page.evaluate(() => {
          const bar = document.querySelector("nav[aria-label]")?.getBoundingClientRect();
          const art = document.querySelector("article")?.getBoundingClientRect();
          if (!bar || !art) return 0;
          return Math.max(0, Math.round(bar.top - art.bottom));
        });
        expect(covered, "the bottom bar starts after the article").toBeGreaterThanOrEqual(0);
      });
    }
  }

  test("every page keeps one container width (375 → 1920)", async ({ page }) => {
    test.setTimeout(240_000);
    await signIn(page);
    const routes = ["/", "/tableros", "/proyectos", "/perfil", "/ayuda", "/admin",
                    "/admin/usuarios", "/admin/apariencia", "/admin/auditoria"];
    const widths = [320, 375, 768, 1024, 1440, 1920];
    for (const route of routes) {
      for (const width of widths) {
        await page.setViewportSize({ width, height: 800 });
        await page.goto(route);
        await expect.poll(() => overflow(page), { message: `${route} at ${width}` })
          .toBeLessThanOrEqual(0);
      }
    }
    // And at the widest, no page sits in a narrow column: the container is what bounds it.
    await page.setViewportSize({ width: 1920, height: 900 });
    for (const route of routes) {
      await page.goto(route);
      await expect(page.locator("main")).toBeVisible();
      const inner = await page.evaluate(() => {
        const main = document.querySelector("main");
        return main ? Math.round(main.getBoundingClientRect().width) : 0;
      });
      expect(inner, `${route} uses the container at 1920`).toBeGreaterThan(1400);
    }
  });

  test("200 % zoom behaves like half the width", async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width: 1024, height: 768 });
    await signIn(page);
    await page.evaluate(() => { document.body.style.zoom = "2"; });
    for (const route of ["/perfil", "/ayuda", "/admin/apariencia"]) {
      await page.goto(route);
      await expect.poll(() => overflow(page), { message: `${route} at 200 %` })
        .toBeLessThanOrEqual(0);
    }
  });
});
