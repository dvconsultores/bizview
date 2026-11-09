import { expect, test, type Page } from "@playwright/test";

// Feature 062 — five phone defects left over after 056b and 059 (specs/062-mobile-fixes-round-2).
//
// Four of the five had been marked done by an earlier feature, because their tests asserted classes
// instead of geometry. So every case here reads a box from the real layout engine: a height, a
// width in px, a bottom edge against a footer's top edge. jsdom cannot do any of it; the unit suite
// pins the wiring (`tests/unit/card-dialog-pie.test.tsx`, `layout-guards.test.ts`).
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SEEDED = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
/** The owner's device, and 059's. */
const PHONES = [{ width: 360, height: 780 }, { width: 393, height: 851 }] as const;
const LAYOUT_REPORT = "ventas-layout";

const settled = (page: Page) =>
  page.evaluate(() => new Promise<void>((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function openReport(page: Page, id = "ventas") {
  await signIn(page);
  await page.goto(`/r/${id}?${SEEDED}`);
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  await settled(page);
}

/**
 * The seeded workspace declares no donut, and the fixture is shared with twenty other suites, so the
 * donut of the owner's evidence ("Vendedores por monto") is declared here — a `donut` over the
 * `detalle` table view, which is the same binding a project would write.
 */
async function withDonut(page: Page) {
  await page.route(`**/api/reports/${LAYOUT_REPORT}*`, async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as {
      layout?: { web?: { components?: Record<string, unknown>[] } };
    };
    body.layout?.web?.components?.push({
      id: "vendedores",
      type: "donut",
      view: "detalle",
      category: "product",
      series: ["net_sales"],
      span: 12,
    });
    await route.fulfill({ response, json: body });
  });
}

// US1 (one provider per row) is proved by `tests/unit/sign-in-phone.test.tsx`: the e2e
// installation has no Google or Telegram credentials, so `/ingresar` renders neither button and a
// geometric case here would assert nothing. The stacking is `space-y-3` + `w-full` with no grid,
// which is a property of the markup rather than of a measurement.

test.describe("the filters sheet on a phone (US2)", () => {
  for (const phone of PHONES) {
    test(`is the whole screen and its last control clears the footer at ${phone.width} px`, async ({ page }) => {
      await page.setViewportSize(phone);
      await openReport(page);
      await page.getByRole("button", { name: /^Parámetros/ }).click();
      const sheet = page.getByTestId("report-sheet");
      await expect(sheet).toBeVisible();
      await settled(page);

      const geometry = await page.evaluate(() => {
        const panel = document.querySelector<HTMLElement>('[data-testid="report-sheet"]')!;
        const footer = panel.querySelector<HTMLElement>("[data-sheet-footer]")!;
        const body = panel.querySelector<HTMLElement>('[role="tabpanel"]')!;
        const last = [...body.querySelectorAll<HTMLElement>("label")].pop() ?? null;
        last?.scrollIntoView({ block: "end" });
        const footerTop = footer.getBoundingClientRect().top;
        return {
          height: Math.round(panel.getBoundingClientRect().height),
          innerHeight: window.innerHeight,
          footerTop: Math.round(footerTop),
          footerBottom: Math.round(footer.getBoundingClientRect().bottom),
          lastBottom: last ? Math.round(last.getBoundingClientRect().bottom) : null,
          bodyPaddingBottom: parseFloat(getComputedStyle(body).paddingBottom),
          bodyScrolls: body.scrollHeight > body.clientHeight,
        };
      });
      // Full screen: 100 dvh, not 85 % and not a card.
      expect(Math.abs(geometry.height - geometry.innerHeight)).toBeLessThanOrEqual(2);
      expect(geometry.footerBottom).toBeLessThanOrEqual(geometry.innerHeight + 1);
      // The body reserves the footer's height, so the last control ends above it — the defect.
      expect(geometry.bodyPaddingBottom).toBeGreaterThan(40);
      expect(geometry.lastBottom).not.toBeNull();
      expect(geometry.lastBottom!).toBeLessThanOrEqual(geometry.footerTop + 1);
    });
  }

  test("uses the whole width: Período and Comparar con share the row at 360 px", async ({ page }) => {
    // The owner: "parameters and filter in mobile need a little bit more wide". Two causes, both
    // geometric: the body's 16 px gutter left 328 px, and the grid's 160 px minimum needed 332 for
    // two columns, so the pair stacked at 360 px and every control read as narrow.
    await page.setViewportSize(PHONES[0]);
    await openReport(page);
    await page.getByRole("button", { name: /^Parámetros/ }).click();
    await expect(page.getByTestId("report-sheet")).toBeVisible();
    await settled(page);

    const measured = await page.evaluate(() => {
      const dialog = document.querySelector<HTMLElement>('[data-testid="report-sheet"]')!;
      const body = dialog.querySelector<HTMLElement>('[role="tabpanel"]')!;
      const box = (label: string) => {
        const field = [...body.querySelectorAll<HTMLElement>("label")]
          .find((element) => (element.textContent ?? "").trim() === label);
        if (!field) return null;
        const control = field.parentElement ?? field;
        const rect = control.getBoundingClientRect();
        return { top: Math.round(rect.top), left: Math.round(rect.left),
                 width: Math.round(rect.width), bottom: Math.round(rect.bottom) };
      };
      return {
        period: box("Período"),
        compare: box("Comparar con"),
        bodyPadding: parseFloat(getComputedStyle(body).paddingLeft),
        bodyWidth: Math.round(body.getBoundingClientRect().width),
        scrollWidth: Math.round(body.scrollWidth),
      };
    });
    expect(measured.period, "the period control must be in the sheet").not.toBeNull();
    expect(measured.compare, "the comparison control must be in the sheet").not.toBeNull();
    // A 12 px gutter, not 16: the controls gain 8 px of width.
    expect(measured.bodyPadding).toBeLessThanOrEqual(12);
    // They share the row (059's promise from 320 px), and each is at least 150 px wide.
    expect(measured.period!.top).toBe(measured.compare!.top);
    expect(measured.compare!.left).toBeGreaterThan(measured.period!.left + measured.period!.width - 1);
    for (const control of [measured.period!, measured.compare!]) {
      expect(control.width, "a control is never narrower than 150 px").toBeGreaterThanOrEqual(150);
    }
    // And nothing overflows the sheet horizontally.
    expect(measured.scrollWidth).toBeLessThanOrEqual(measured.bodyWidth + 1);
  });

  test("closes with the phone's back button and leaves focus on the opener", async ({ page }) => {
    await page.setViewportSize(PHONES[0]);
    await openReport(page);
    const opener = page.getByRole("button", { name: /^Filtros/ });
    await opener.click();
    await expect(page.getByTestId("report-sheet")).toBeVisible();
    await page.goBack();
    await expect(page.getByTestId("report-sheet")).toHaveCount(0);
    // Focus back on the control that opened it (059 T012, still true after 062).
    const focused = await page.evaluate(() => document.activeElement?.textContent ?? "");
    expect(focused).toContain("Filtros");
  });
});

test.describe("the maximized card's header (US3)", () => {
  test("titles a KPI with its metric's label on one line, never the component id", async ({ page }) => {
    await page.setViewportSize(PHONES[0]);
    await openReport(page, LAYOUT_REPORT);
    await page.locator('[data-layout-id="resumen_kpi"] [data-maximize]').click();
    const dialog = page.locator("[data-card-dialog]");
    await expect(dialog).toBeVisible();
    await settled(page);

    const header = await page.evaluate(() => {
      const root = document.querySelector<HTMLElement>("[data-card-dialog-header]")!;
      const title = root.querySelector<HTMLElement>("h2")!;
      const actions = title.nextElementSibling as HTMLElement;
      const buttons = [...actions.querySelectorAll("button")].map((button) => {
        const rect = button.getBoundingClientRect();
        return { width: Math.round(rect.width), height: Math.round(rect.height) };
      });
      return {
        text: title.textContent?.trim() ?? "",
        titleWidth: Math.round(title.getBoundingClientRect().width),
        headerWidth: Math.round(root.getBoundingClientRect().width),
        oneLine: title.scrollHeight === title.clientHeight,
        buttons,
      };
    });
    // The metric's label — "Ventas netas" in the seeded report — not `resumen_kpi`.
    expect(header.text).toBe("Ventas netas");
    expect(header.text).not.toMatch(/^k_|resumen_kpi/);
    expect(header.oneLine, "the title must not wrap").toBe(true);
    // The brief asked for "≥ 60 % of the header", which is arithmetically impossible on a 360 px
    // phone: the header is 328 px wide and three 44 px actions plus their gaps are ~140 px, leaving
    // 188 px for the title (57 %). What the requirement is really about — the title is not squeezed
    // to a sliver and never stacks — is what is asserted, at the width the arithmetic allows.
    expect(header.titleWidth / header.headerWidth).toBeGreaterThanOrEqual(0.5);
    for (const button of header.buttons) {
      expect(button.height, "every action is a 44 px target").toBeGreaterThanOrEqual(44);
    }
  });

  test("keeps a donut's title on one line and the chips on their own row", async ({ page }) => {
    await page.setViewportSize(PHONES[0]);
    await withDonut(page);
    await openReport(page, LAYOUT_REPORT);
    // The injected donut is the last card of the layout.
    await page.locator('[data-layout-id="vendedores"] [data-maximize]').click();
    const dialog = page.locator("[data-card-dialog]");
    await expect(dialog).toBeVisible();
    await settled(page);
    const measured = await page.evaluate(() => {
      const root = document.querySelector<HTMLElement>("[data-card-dialog-header]")!;
      const title = root.querySelector<HTMLElement>("h2")!;
      const chips = root.querySelector<HTMLElement>("[data-dialog-meta]");
      return {
        text: title.textContent?.trim() ?? "",
        lines: Math.round(title.getBoundingClientRect().height),
        chipsTop: chips ? Math.round(chips.getBoundingClientRect().top) : null,
        titleBottom: Math.round(title.getBoundingClientRect().bottom),
      };
    });
    // A donut names no title of its own, so the metric label of the view it draws titles it.
    expect(measured.text).not.toBe("vendedores");
    expect(measured.text.length).toBeGreaterThan(2);
    // One line of an 18 px heading, not one letter per line down the edge (the defect).
    expect(measured.lines).toBeLessThan(40);
    if (measured.chipsTop !== null) {
      expect(measured.chipsTop).toBeGreaterThanOrEqual(measured.titleBottom - 1);
    }
  });
});

test.describe("the donut on a phone (US4)", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`draws a ring in the ${scheme} theme, in the card and maximized`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.setViewportSize(PHONES[0]);
      await withDonut(page);
      await openReport(page, LAYOUT_REPORT);

      const cell = page.locator('[data-layout-id="vendedores"]');
      await expect(cell, "the injected donut must render").toBeVisible();
      const ring = cell.locator("svg").first();
      await expect(ring).toBeVisible();
      const cardRing = (await ring.boundingBox())!;
      const cardCell = (await cell.boundingBox())!;
      const cardLegend = (await cell.locator("ul").first().boundingBox())!;
      expect(cardRing.width, "the card's ring is drawn, not clipped to nothing")
        .toBeGreaterThanOrEqual(200);
      expect(cardRing.width, "the ring fits its card").toBeLessThanOrEqual(cardCell.width);
      expect(cardLegend.y, "the legend sits under the ring on a phone")
        .toBeGreaterThanOrEqual(cardRing.y + cardRing.height - 1);

      await cell.locator("[data-maximize]").click();
      const dialog = page.locator("[data-card-dialog]");
      await expect(dialog).toBeVisible();
      await settled(page);
      const bigRing = (await dialog.locator("[data-card-dialog-body] svg").first().boundingBox())!;
      const body = (await dialog.locator("[data-card-dialog-body]").boundingBox())!;
      expect(bigRing.width, "the maximized ring grows with the dialog").toBeGreaterThanOrEqual(300);
      expect(bigRing.x + bigRing.width, "and does not overflow it").toBeLessThanOrEqual(body.x + body.width + 1);
    });
  }
});

test.describe("the source form's actions (US5)", () => {
  for (const phone of PHONES) {
    test(`scroll with the form at ${phone.width} px and never cover a field`, async ({ page }) => {
      await page.setViewportSize(phone);
      await signIn(page);
      await page.goto("/admin/fuentes/nueva");
      await expect(page.locator("[data-source-actions]")).toBeVisible();
      await settled(page);

      const measured = await page.evaluate(() => {
        const actions = document.querySelector<HTMLElement>("[data-source-actions]");
        if (!actions) return null;
        const floating = [...document.querySelectorAll<HTMLElement>("main *")]
          .filter((node) => {
            const position = getComputedStyle(node).position;
            return position === "sticky" || position === "fixed";
          })
          .map((node) => `${node.tagName.toLowerCase()}.${node.className}`.slice(0, 90));
        // The block sits after every field in document order.
        const fields = [...document.querySelectorAll<HTMLElement>("main label")];
        const lastField = fields.at(-1) ?? null;
        return {
          floating,
          actionsTop: Math.round(actions.getBoundingClientRect().top + window.scrollY),
          lastFieldTop: lastField
            ? Math.round(lastField.getBoundingClientRect().top + window.scrollY)
            : null,
          buttons: [...actions.querySelectorAll("button")].map((button) =>
            (button.textContent ?? "").trim()),
        };
      });
      expect(measured, "the actions block must be identifiable").not.toBeNull();
      expect(measured!.floating, "nothing floats over the form").toEqual([]);
      if (measured!.lastFieldTop !== null) {
        expect(measured!.actionsTop).toBeGreaterThanOrEqual(measured!.lastFieldTop);
      }
      expect(measured!.buttons.slice(0, 2)).toEqual(["Guardar", "Probar conexión"]);
    });
  }

  test("orders Guardar, Probar conexión and then Eliminar fuente, separated", async ({ page }) => {
    await page.setViewportSize(PHONES[0]);
    await signIn(page);
    await page.goto("/admin/fuentes");
    await page.locator("a[href^='/admin/fuentes/']").first().click();
    await expect(page.locator("[data-source-actions]")).toBeVisible();
    await settled(page);
    const buttons = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("[data-source-actions] button")].map(
        (button) => (button.textContent ?? "").trim(),
      ));
    expect(buttons).toContain("Eliminar fuente");
    expect(buttons.indexOf("Guardar")).toBeLessThan(buttons.indexOf("Probar conexión"));
    expect(buttons.indexOf("Probar conexión")).toBeLessThan(buttons.indexOf("Eliminar fuente"));
  });
});

test.describe("the phone sweep (SC-001)", () => {
  const routes = ["/", "/tableros", "/perfil", "/admin", "/admin/fuentes", "/admin/integraciones"];

  for (const phone of PHONES) {
    for (const scheme of ["light", "dark"] as const) {
      test(`no horizontal scroll at ${phone.width} px, ${scheme}`, async ({ page }) => {
        await page.setViewportSize(phone);
        await page.emulateMedia({ colorScheme: scheme });
        await signIn(page);
        for (const route of routes) {
          await page.goto(route);
          await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
          await settled(page);
          const overflow = await page.evaluate(() => ({
            scrollWidth: document.documentElement.scrollWidth,
            viewport: document.documentElement.clientWidth,
          }));
          expect(overflow.scrollWidth, `${route} at ${phone.width} px (${scheme})`)
            .toBeLessThanOrEqual(overflow.viewport);
        }
      });
    }
  }
});
