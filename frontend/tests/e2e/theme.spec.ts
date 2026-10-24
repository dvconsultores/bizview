import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { reportAction } from "./fixtures/report-action";

// Feature 006 — dark mode (specs/006-dark-mode/quickstart.md). The theme is stored on the super
// user's account, so every test puts it back to "system" for the suites that run after it.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
const ROUTES = [
  "/", `/r/ventas?${SELECTION}`, "/d/ventas", "/perfil", "/cambiar-clave", "/seguridad/doble-factor",
  "/admin", "/admin/usuarios", "/admin/usuarios/nuevo", "/admin/auditoria", "/admin/ia",
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
// WebKit may report stale computed styles right after a theme switch, so wait two animation frames.
const settled = (page: Page) => page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r()))));

async function expectAccessible(page: Page, where: string, { waitIdle = true }: { waitIdle?: boolean } = {}) {
  if (waitIdle) await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function resetAccountTheme(browser: Browser) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signIn(page);
  const r = await page.request.patch("/api/me/preferences", {
    data: { theme: "system" }, headers: { "X-Requested-With": "fetch" },
  });
  expect(r.status()).toBe(200);
  await context.close();
}

test.afterEach(async ({ browser }) => resetAccountTheme(browser));

for (const scheme of ["dark", "light"] as const) {
  test.describe(`${scheme} device`, () => {
    test.use({ colorScheme: scheme });

    test(`every screen follows the device and passes axe (${scheme})`, async ({ page }) => {
      await page.goto("/ingresar");
      expect(await theme(page)).toBe(scheme);
      await expectAccessible(page, "/ingresar");
      await signIn(page);
      for (const route of ROUTES) {
        await page.goto(route);
        expect(await theme(page), route).toBe(scheme);
        await expectAccessible(page, route);
      }
      await page.goto("/");
      await page.getByRole("button", { name: "Menú de cuenta" }).click();
      await expect(page.getByRole("menu")).toBeVisible();
      await expectAccessible(page, "account menu");

      // (a) The signed-in user's own detail screen must also follow the device and pass axe.
      const me = await (await page.request.get("/api/me")).json() as { id: number };
      await page.goto(`/admin/usuarios/${me.id}`);
      expect(await theme(page)).toBe(scheme);
      await expectAccessible(page, "user detail");

      // (b) An open step-up dialog must follow the device and pass axe.
      await page.goto("/admin/tokens");
      await page.getByLabel("Nombre").fill("axe dialog");
      await page.getByRole("button", { name: "Crear token" }).click();
      const dialog = page.getByRole("region", { name: "Confirma tu contraseña" });
      await expect(dialog).toBeVisible();
      await expectAccessible(page, "dialog", { waitIdle: false });
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
    });
  });
}

test.describe("device appearance", () => {
  test.use({ colorScheme: "dark" });

  test("no flash: the theme is set before the app code runs", async ({ page }) => {
    await page.route("**/assets/*.js", (r) => r.abort());
    // SC-004: 10 consecutive loads with app code blocked must never flash.
    for (let i = 0; i < 10; i++) {
      await page.goto("/ingresar");
      expect(await theme(page), `load ${i + 1}`).toBe("dark");
    }
    await page.addInitScript(() => localStorage.setItem("bizview.theme", "light"));
    for (let i = 0; i < 10; i++) {
      await page.goto("/ingresar");
      expect(await theme(page), `light load ${i + 1}`).toBe("light");
    }
  });

  test("with Sistema the open screen follows the device live, keeping its state", async ({ page }) => {
    await signIn(page);
    await page.goto("/admin/usuarios");
    const search = page.getByLabel("Buscar por nombre o correo");
    await search.fill("ana");
    await page.emulateMedia({ colorScheme: "light" });
    await expect.poll(() => theme(page)).toBe("light");
    await page.emulateMedia({ colorScheme: "dark" });
    await expect.poll(() => theme(page)).toBe("dark");
    await expect(search).toHaveValue("ana");
  });
});

test.describe("chosen theme", () => {
  test.use({ colorScheme: "light" });

  test("profile choice applies at once and follows the user to another device", async ({ page, browser }) => {
    await signIn(page);
    await page.goto("/perfil");
    const saved = page.waitForResponse((r) => r.url().endsWith("/api/me/preferences") && r.ok());
    await page.getByRole("radio", { name: "Oscuro" }).click();
    await saved;
    expect(await theme(page)).toBe("dark");
    await expect(page.getByRole("radio", { name: "Oscuro" })).toHaveAttribute("aria-checked", "true");

    await page.emulateMedia({ colorScheme: "dark" });
    await page.emulateMedia({ colorScheme: "light" });
    expect(await theme(page)).toBe("dark");                      // explicit choice ignores the device

    const other = await browser.newContext({ colorScheme: "light" });
    const second = await other.newPage();
    await signIn(second);
    await expect.poll(() => theme(second)).toBe("dark");          // SC-003
    await other.close();

    await page.goto("/perfil");
    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    await expect(page).toHaveURL(/ingresar/);
    await page.reload();
    expect(await theme(page)).toBe("dark");                      // FR-007: last choice on this device
  });

  test("account menu switches in two taps from a report", async ({ page }) => {
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await page.getByRole("button", { name: "Menú de cuenta" }).click();       // tap 1
    await page.getByRole("menuitemradio", { name: "Oscuro" }).click();        // tap 2
    expect(await theme(page)).toBe("dark");
    await expect(page.getByRole("heading", { level: 1, name: "Ventas" })).toBeVisible();
  });

  test("a failed save keeps the theme and says it was not saved", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/me/preferences", (r) => r.fulfill({ status: 500, body: "{}" }));
    await page.goto("/perfil");
    await page.getByRole("radio", { name: "Oscuro" }).click();
    expect(await theme(page)).toBe("dark");
    await settled(page);
    await expect(page.getByText("no se pudo guardar en tu cuenta")).toBeVisible();
    await expectAccessible(page, "toast");
  });
});

test.describe("chosen light theme", () => {
  test.use({ colorScheme: "dark" });

  test("Claro on a dark device applies at once, ignores the device and follows the user", async ({ page, browser }) => {
    await signIn(page);
    await page.goto("/perfil");

    const saveResponse = page.waitForResponse(
      (r) => r.url().endsWith("/api/me/preferences") && r.ok(),
    );
    await page.getByRole("radio", { name: "Claro" }).click();
    const save = await saveResponse;
    expect(await save.json()).toEqual({ theme: "light", locale: null });

    await expect.poll(() => theme(page)).toBe("light"); // US2/AC1

    await expect(page.getByRole("radio", { name: "Claro" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("radio", { name: "Oscuro" })).toHaveAttribute("aria-checked", "false");

    await page.emulateMedia({ colorScheme: "light" });
    await expect.poll(() => theme(page)).toBe("light");
    await page.emulateMedia({ colorScheme: "dark" });
    await expect.poll(() => theme(page)).toBe("light"); // US2/AC3

    const other = await browser.newContext({ colorScheme: "dark" });
    const second = await other.newPage();
    await signIn(second);
    await expect.poll(() => theme(second)).toBe("light"); // SC-003
    await other.close();

    await page.goto("/perfil");
    await page.getByRole("button", { name: "Cerrar sesión" }).click();
    await expect(page).toHaveURL(/ingresar/);
    await page.reload();
    await expect.poll(() => theme(page)).toBe("light"); // FR-007
  });

  test("account menu switches back and forth, and Sistema follows the device again", async ({ page }) => {
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);

    await page.getByRole("button", { name: "Menú de cuenta" }).click();

    const steps: Array<{ label: string; preference: string; resolved: string }> = [
      { label: "Oscuro", preference: "dark", resolved: "dark" },
      { label: "Claro", preference: "light", resolved: "light" },
      { label: "Sistema", preference: "system", resolved: "dark" },
      { label: "Oscuro", preference: "dark", resolved: "dark" },
      { label: "Claro", preference: "light", resolved: "light" },
    ];

    for (const step of steps) {
      const saveResponse = page.waitForResponse(
        (r) => r.url().endsWith("/api/me/preferences") && r.ok(),
      );
      await page.getByRole("menuitemradio", { name: step.label }).click();
      const save = await saveResponse;
      expect(await save.json()).toEqual({ theme: step.preference, locale: null }); // FR-002/SC-002
      await expect.poll(() => theme(page)).toBe(step.resolved); // FR-004
      await expect(page.getByRole("menuitemradio", { name: step.label })).toHaveAttribute("aria-checked", "true");

      if (step.label === "Sistema") {
        await page.emulateMedia({ colorScheme: "light" });
        await expect.poll(() => theme(page)).toBe("light");
        await page.emulateMedia({ colorScheme: "dark" });
        await expect.poll(() => theme(page)).toBe("dark"); // FR-005
      }
    }

    await expect(page.getByRole("heading", { level: 1, name: "Ventas" })).toBeVisible();
    await page.reload();
    await expect.poll(() => theme(page)).toBe("light"); // FR-007
  });
});

test.describe("reports", () => {
  test.use({ colorScheme: "dark" });

  test("report is readable in dark and its PDF is the same as in light", async ({ page }) => {
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(page.getByRole("heading", { name: "Tendencia: Ventas netas" })).toBeVisible();
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    await expect(page.locator("svg path[stroke-dasharray]")).toHaveCount(1);   // previous period
    await expectAccessible(page, "report");

    const pdf = async () => {
      const download = page.waitForEvent("download");
      await reportAction(page, "Descargar PDF");
      const stream = await (await download).createReadStream();
      const chunks: Buffer[] = [];
      for await (const c of stream) chunks.push(c as Buffer);
      return Buffer.concat(chunks).toString("latin1")
        .replace(/\/(CreationDate|ModDate) \([^)]*\)/g, "").replace(/\/ID \[[^\]]*\]/g, "");
    };
    const dark = await pdf();
    await page.emulateMedia({ colorScheme: "light" });
    await expect.poll(() => theme(page)).toBe("light");
    expect(await pdf()).toBe(dark);                                            // FR-012
  });
});
