import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 012 — report parameters panel (specs/012-report-params-panel/spec.md).
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SELECTION = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

const theme = (page: Page) => page.evaluate(() => document.documentElement.dataset.theme);

function countDataRequests(page: Page) {
  const state = { count: 0 };
  const listener = (request: { url: () => string }) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/reports/ventas/data") state.count += 1;
  };
  page.on("request", listener);
  return {
    get count() {
      return state.count;
    },
    reset() {
      state.count = 0;
    },
    dispose() {
      page.off("request", listener);
    },
  };
}

async function expectNoHorizontalScroll(page: Page) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
    .toBeLessThanOrEqual(0);
}

async function expectAccessible(
  page: Page,
  where: string,
  { waitIdle = true }: { waitIdle?: boolean } = {},
) {
  if (waitIdle) await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(
    bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`),
  ).toEqual([]);
}

const kpi = (page: Page, label: string) =>
  page.getByRole("region", { name: "Indicadores" }).getByRole("listitem").filter({ hasText: label });

const panel = (page: Page) => page.getByRole("complementary", { name: "Filtros y controles" });
const filtersView = (page: Page) => page.getByRole("region", { name: "Filtros y controles" });

async function readDownload(page: Page, trigger: () => Promise<void>) {
  const downloadPromise = page.waitForEvent("download");
  await trigger();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk as Buffer);
  return { download, text: Buffer.concat(chunks).toString("utf8") };
}

function assertCsv(text: string) {
  expect(text.startsWith("﻿")).toBe(true);
  const lines = text.split("\r\n");
  expect(lines[0].startsWith("﻿Producto;Ventas netas;Participación (%)")).toBe(true);
  expect(lines.some((line) => line.startsWith("Alimento premium;7.5;"))).toBe(true);
  expect(lines.some((line) => line.startsWith("Vacuna triple;4.25;"))).toBe(true);
  expect(lines.some((line) => line.includes("7,5"))).toBe(false);
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 900 }, colorScheme: "light" });

  test("three edits apply once, survive reload; multi-value; chip removal; Limpiar todo", async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    await expect(panel(page)).toBeVisible();
    await expect(page.getByTestId("pending-status")).toHaveText("Sin cambios pendientes");
    await expect(panel(page).getByRole("button", { name: "Aplicar filtros" })).toBeDisabled();

    const counter = countDataRequests(page);
    counter.reset();

    await panel(page).getByLabel("Desde").fill("2026-09-26");
    await panel(page).getByLabel("Comparar con").selectOption("previous_year");
    await panel(page).getByRole("combobox", { name: "Producto" }).click();
    await panel(page).getByRole("option", { name: "Vacuna triple" }).click();

    await expect(page.getByTestId("pending-status")).toHaveText("3 cambios sin aplicar");
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    expect(counter.count).toBe(0);

    await panel(page).getByRole("button", { name: "Aplicar filtros" }).click();
    await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
    await page.waitForLoadState("networkidle");
    expect(counter.count).toBe(1);
    await expect(page).toHaveURL(/from=2026-09-26/);
    await expect(page).toHaveURL(/compare=previous_year/);
    await expect(page).toHaveURL(/filter\.product=Vacuna/);
    await expect(page.getByTestId("pending-status")).toHaveText("Sin cambios pendientes");
    await expect(
      page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }),
    ).toBeVisible();

    await page.reload();
    await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
    await expect(
      page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }),
    ).toBeVisible();

    counter.reset();
    await panel(page).getByRole("combobox", { name: "Producto" }).click();
    await panel(page).getByRole("option", { name: "Alimento premium" }).click();
    await panel(page).getByRole("button", { name: "Aplicar filtros" }).click();
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
    await page.waitForLoadState("networkidle");
    expect(counter.count).toBe(1);
    expect(new URL(page.url()).searchParams.getAll("filter.product").sort()).toEqual([
      "Alimento premium",
      "Vacuna triple",
    ]);

    counter.reset();
    await page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }).click();
    await expect(kpi(page, "Ventas netas")).toContainText(/7,50\sUSD/);
    await page.waitForLoadState("networkidle");
    expect(counter.count).toBe(1);
    expect(new URL(page.url()).searchParams.getAll("filter.product")).toEqual([
      "Alimento premium",
    ]);

    counter.reset();
    await panel(page).getByRole("button", { name: "Limpiar todo" }).click();
    await expect(page).toHaveURL(/period=mtd/);
    await expect(page).toHaveURL(/compare=previous_period/);
    expect(new URL(page.url()).searchParams.getAll("filter.product")).toEqual([]);
    await page.waitForLoadState("networkidle");
    expect(counter.count).toBe(1);
    await expect(page.getByRole("button", { name: /^Quitar filtro/ })).toHaveCount(0);

    counter.dispose();
  });

  test("invalid custom range is not applied", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    const counter = countDataRequests(page);
    counter.reset();
    await panel(page).getByLabel("Hasta").fill("2026-09-20");
    await panel(page).getByRole("button", { name: "Aplicar filtros" }).click();
    await expect(page.getByText("La fecha final no puede ser anterior a la inicial.")).toBeVisible();
    await expect(page).toHaveURL(/to=2026-09-28/);
    expect(counter.count).toBe(0);

    counter.dispose();
  });

  test("CSV from the card menu and from the panel", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

    const cardCsv = await readDownload(page, async () => {
      await page.getByRole("button", { name: "Opciones de Ventas netas por Producto" }).click();
      await page.getByRole("button", { name: "Descargar CSV" }).click();
    });
    expect(cardCsv.download.suggestedFilename()).toBe(
      "ventas-2026-09-27-2026-09-28-ventas-netas-por-producto.csv",
    );
    assertCsv(cardCsv.text);

    const panelCsv = await readDownload(page, async () => {
      await panel(page).getByRole("radio", { name: "CSV" }).check();
      await panel(page).getByRole("button", { name: "Generar reporte" }).click();
    });
    expect(panelCsv.download.suggestedFilename()).toBe("ventas-2026-09-27-2026-09-28.csv");
    assertCsv(panelCsv.text);
  });

  test("collapse is remembered", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.endsWith("-320"), "desktop layout checked once per engine");
    await signIn(page);
    await page.goto(`/r/ventas?${SELECTION}`);
    await expect(panel(page)).toBeVisible();

    await panel(page).getByRole("button", { name: "Ocultar filtros y controles" }).click();
    await expect(panel(page)).toBeHidden();
    await expect(page.getByRole("button", { name: "Mostrar filtros y controles" })).toBeVisible();

    await page.reload();
    await expect(panel(page)).toBeHidden();
    await page.getByRole("button", { name: "Mostrar filtros y controles" }).click();
    await expect(panel(page)).toBeVisible();
  });
});

test("Filtros view: back discards, apply closes and reloads once", async ({ page }) => {
  await signIn(page);
  await page.goto(`/r/ventas?${SELECTION}`);
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);
  await expect(panel(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Filtros/ })).toBeVisible();

  const counter = countDataRequests(page);
  counter.reset();

  await page.getByRole("button", { name: /^Filtros/ }).click();
  await expect(filtersView(page)).toBeVisible();
  await filtersView(page).getByLabel("Comparar con").selectOption("previous_year");
  await filtersView(page).getByRole("button", { name: "Volver" }).click();
  await expect(filtersView(page)).toBeHidden();
  await expect(page).toHaveURL(/compare=previous_period/);
  expect(counter.count).toBe(0);
  await expect(kpi(page, "Ventas netas")).toContainText(/11,75\sUSD/);

  await page.getByRole("button", { name: /^Filtros/ }).click();
  await expect(filtersView(page)).toBeVisible();
  await expect(filtersView(page).getByLabel("Comparar con")).toHaveValue("previous_period");

  await filtersView(page).getByRole("combobox", { name: "Producto" }).click();
  await filtersView(page).getByRole("option", { name: "Vacuna triple" }).click();
  await filtersView(page).getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(filtersView(page)).toBeHidden();
  await expect(page).toHaveURL(/filter\.product=Vacuna/);
  await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
  await page.waitForLoadState("networkidle");
  expect(counter.count).toBe(1);
  await expect(page.getByRole("button", { name: "Filtros (1)" })).toBeVisible();

  await page.getByRole("button", { name: "Filtros (1)" }).click();
  await expect(filtersView(page)).toBeVisible();
  await filtersView(page).getByLabel("Comparar con").selectOption("previous_year");
  counter.reset();
  await page.goBack();
  await expect(filtersView(page)).toBeHidden();
  await expect(page).toHaveURL(/filter\.product=Vacuna/);
  await expect(page).toHaveURL(/compare=previous_period/);
  expect(counter.count).toBe(0);

  await expectNoHorizontalScroll(page);

  counter.dispose();
});

test.describe("accessibility", () => {
  for (const scheme of ["dark", "light"] as const) {
    test.describe(`${scheme} theme`, () => {
      test.use({ colorScheme: scheme });

      test("report, filters view, open listbox, and desktop panel are accessible", async ({
        page,
      }, testInfo) => {
        await signIn(page);
        await page.goto(`/r/ventas?${SELECTION}&filter.product=Vacuna+triple`);   // old single-value link
        await expect(kpi(page, "Ventas netas")).toContainText(/4,25\sUSD/);
        await expect(
          page.getByRole("button", { name: "Quitar filtro Producto: Vacuna triple" }),
        ).toBeVisible();
        expect(await theme(page)).toBe(scheme);

        await expectAccessible(page, "report");
        await expectNoHorizontalScroll(page);

        await page.getByRole("button", { name: "Filtros (1)" }).click();
        await expect(filtersView(page)).toBeVisible();
        await expectAccessible(page, "filters view");
        await expectNoHorizontalScroll(page);

        await filtersView(page).getByRole("combobox", { name: "Producto" }).click();
        await expect(page.getByRole("listbox")).toBeVisible();
        await expectAccessible(page, "listbox", { waitIdle: false });

        await filtersView(page).getByRole("button", { name: "Volver" }).click();
        await expect(filtersView(page)).toBeHidden();

        if (!testInfo.project.name.endsWith("-320")) {
          await page.setViewportSize({ width: 1280, height: 900 });
          await expect(panel(page)).toBeVisible();
          // WebKit can report the phone styles for a moment after a resize; let it re-style first.
          await page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r()))));
          await expectAccessible(page, "desktop panel");
        }
      });
    });
  }
});
