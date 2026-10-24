// Feature 010 — Customer A look (specs/010-visual-redesign/contracts/design-system.md).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const ROUTES = [
  "/", "/tableros", `/r/ventas?${SELECTION}`, "/d/ventas", "/perfil", "/cambiar-clave", "/seguridad/doble-factor",
  "/admin", "/admin/usuarios", "/admin/usuarios/nuevo", "/admin/auditoria", "/admin/ia", "/admin/apariencia",
  "/admin/fuentes", "/admin/fuentes/nueva", "/admin/seguridad", "/admin/espacio",
  "/admin/integraciones", "/admin/tokens", "/no-autorizado", "/no-existe",
];

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

const theme = (page: Page) => page.evaluate(() => document.documentElement.dataset.theme);

async function expectAccessible(page: Page, where: string, { waitIdle = true }: { waitIdle?: boolean } = {}) {
  if (waitIdle) await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function expectHeaderCard(page: Page, route: string) {
  const result = await page.evaluate(() => {
    const h1s = Array.from(document.querySelectorAll("h1"));
    const h1 = h1s.find((el) => el.getClientRects().length > 0);
    if (!h1) return { card: false, radius: 0, foundH1: false };

    const probe = document.createElement("div");
    probe.style.borderRadius = "var(--radius-card)";
    document.body.appendChild(probe);
    const cardRadius = parseFloat(getComputedStyle(probe).borderTopLeftRadius);
    probe.remove();
    if (!(cardRadius > 0)) return { card: false, radius: cardRadius, foundH1: true };

    let current: HTMLElement | null = h1.parentElement;
    while (current && current !== document.body) {
      const cs = getComputedStyle(current);
      const radius = parseFloat(cs.borderTopLeftRadius);
      const hasBackground = cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== "transparent";
      const hasImage = cs.backgroundImage !== "none";
      if (radius >= cardRadius - 0.5 && (hasBackground || hasImage)) {
        return { card: true, radius, foundH1: true };
      }
      current = current.parentElement;
    }
    return { card: false, radius: cardRadius, foundH1: true };
  });
  expect(result, `${route} header card`).toEqual({ card: true, radius: expect.any(Number), foundH1: true });
}

async function expectActiveLink(page: Page, route: string, label: string) {
  await page.goto(route);
  await expect(page.locator("aside")).toBeVisible();
  const active = page.locator('aside nav a[aria-current="page"]');
  await expect(active).toHaveCount(1);
  await expect(active).toBeVisible();
  await expect(active).toHaveText(label);
  const isDistinct = await active.evaluate((el) => {
    const aside = el.closest("aside");
    if (!aside) return false;
    const cs = getComputedStyle(el);
    const asideBg = getComputedStyle(aside).backgroundColor;
    const hasImage = cs.backgroundImage !== "none";
    const hasOpaqueBg = cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== "transparent";
    return hasImage || (hasOpaqueBg && cs.backgroundColor !== asideBg);
  });
  expect(isDistinct, `${route} active link distinct from sidebar`).toBe(true);
}

/** SC-001: walking up from the report title, the first max-width is the app container
 * (`max-w-screen-2xl`, 1536 px). The old page-level `max-w-7xl` (1280 px) would be found first. */
async function expectReportContainer(page: Page) {
  const info = await page.evaluate(() => {
    const h1 = Array.from(document.querySelectorAll("h1")).find((el) => el.getClientRects().length > 0);
    if (!h1) return null;
    let el: HTMLElement | null = h1.parentElement;
    while (el && el !== document.body) {
      const maxWidth = getComputedStyle(el).maxWidth;
      if (maxWidth !== "none") {
        return {
          maxWidth,
          width: Math.round(el.getBoundingClientRect().width),
          viewport: window.innerWidth,
        };
      }
      el = el.parentElement;
    }
    return { maxWidth: "none", width: Math.round(h1.getBoundingClientRect().width), viewport: window.innerWidth };
  });
  expect(info, "the report title is on screen").not.toBeNull();
  expect(info!.maxWidth, "the report uses the app container").toBe("1536px");
  if (info!.viewport > 1600) {
    expect(info!.width).toBeGreaterThan(1500);
  }
}

async function checkRoutes(page: Page, scheme: "dark" | "light") {
  // 19 routes, each with axe, against the external BI database: well past the 60 s default.
  test.setTimeout(120_000);
  for (const route of ROUTES) {
    await page.goto(route);
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    expect(await theme(page), `theme ${route}`).toBe(scheme);
    if (route === "/") {
      await expect(page.getByRole("heading", { level: 1 })).toContainText("Bienvenido de nuevo");
    }
    await expectHeaderCard(page, route);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), { message: route }).toBeLessThanOrEqual(0);
    await expectAccessible(page, route);
  }
}

for (const scheme of ["dark", "light"] as const) {
  test.describe(`${scheme} device`, () => {
    test.use({ colorScheme: scheme });

    test.describe("project width", () => {
      test("design contract across routes", async ({ page }) => {
        await signIn(page);
        await checkRoutes(page, scheme);
        await expect(page.locator("aside")).toBeHidden();
      });
    });

    test.describe("desktop 1920", () => {
      test.use({ viewport: { width: 1920, height: 1080 } });

      test("design contract across routes", async ({ page }, testInfo) => {
        test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");

        await signIn(page);
        await checkRoutes(page, scheme);
        await page.goto(`/r/ventas?${SELECTION}`);
        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
        await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
        await expectReportContainer(page);
        await expectActiveLink(page, "/", "Inicio");
        await expectActiveLink(page, "/admin/usuarios", "Administración");   // sections live under it
      });
    });
  });
}
