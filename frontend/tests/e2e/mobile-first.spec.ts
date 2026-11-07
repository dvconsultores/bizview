import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 059 — the phone-sized sign-in screen and the Filtros | Parámetros sheet
// (specs/059-adapt-mobile-first). The evidence in the spec is geometric ("the toggle covers the
// product name", "the sheet opens at 72 % and wastes a quarter of the screen", "the footer covers the
// last control"), so the proof is geometric too: bounding boxes read from the real layout engine at
// the widths the spec names. jsdom cannot measure any of it; the unit tests pin the classes.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const SEEDED = "period=custom&from=2026-09-27&to=2026-09-28&compare=previous_period";
/** The production evidence: an Android phone, 393 × 851 CSS px, dark theme. */
const PHONE = { width: 393, height: 851 } as const;
/** The "one screen, no scroll" case of the spec (A). */
const SHORT_PHONE = { width: 393, height: 640 } as const;
const FLAT_PHONE = { width: 360, height: 740 } as const;
const WIDTHS = [360, 393, 414, 768, 1280] as const;

const settled = (page: Page) =>
  page.evaluate(() =>
    new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function openReport(page: Page) {
  await signIn(page);
  await page.goto(`/r/ventas?${SEEDED}`);
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  await settled(page);
}

const setScheme = async (page: Page, scheme: "light" | "dark") => {
  await page.emulateMedia({ colorScheme: scheme });
  await settled(page);
};

/** Nothing wider than the viewport: the horizontal-scroll check of part C. */
async function overflows(page: Page) {
  return page.evaluate(() => {
    const viewport = document.documentElement.clientWidth;
    const wide = [...document.querySelectorAll<HTMLElement>("body *")]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.right > viewport + 1;
      })
      .slice(0, 5)
      .map((element) => `${element.tagName.toLowerCase()}.${element.className}`.slice(0, 120));
    return { scrollWidth: document.documentElement.scrollWidth, viewport, wide };
  });
}

test.describe("sign-in on a phone", () => {
  test("fits one 393 × 640 screen and the language toggle never covers the header", async ({ page }) => {
    await page.setViewportSize(SHORT_PHONE);
    await page.goto("/ingresar");
    await settled(page);

    const overflow = await overflows(page);
    expect(overflow.scrollWidth, "no horizontal scroll").toBeLessThanOrEqual(overflow.viewport);
    // One screen: the card and every control of the form are inside the viewport.
    const boxes = await page.evaluate(() => {
      const box = (selector: string) => {
        const element = document.querySelector<HTMLElement>(selector);
        if (!element) return null;
        const { top, bottom, left, right } = element.getBoundingClientRect();
        return { top, bottom, left, right };
      };
      return {
        header: box("main, form, h1"),
        form: box("form"),
        submit: box("form button[type=submit]"),
        toggle: box('[role="radiogroup"]'),
      };
    });
    expect(boxes.form).not.toBeNull();
    expect(boxes.form!.bottom).toBeLessThanOrEqual(SHORT_PHONE.height + 1);
    expect(boxes.submit).not.toBeNull();
    expect(boxes.submit!.bottom).toBeLessThanOrEqual(SHORT_PHONE.height + 1);
    // The toggle (Español | English) is below the product name, not over it.
    const headerText = page.locator("p", { hasText: /Bizview/i }).first();
    const headerBox = await headerText.boundingBox();
    const toggleBox = (await page.locator('[role="radiogroup"]').boundingBox())!;
    expect(headerBox).not.toBeNull();
    const overlaps =
      toggleBox.x < headerBox!.x + headerBox!.width &&
      headerBox!.x < toggleBox.x + toggleBox.width &&
      toggleBox.y < headerBox!.y + headerBox!.height &&
      headerBox!.y < toggleBox.y + toggleBox.height;
    expect(overlaps, "the toggle must not intersect the header text").toBe(false);
    expect(toggleBox.y).toBeGreaterThanOrEqual(headerBox!.y + headerBox!.height - 1);
  });

  test("puts both providers side by side and the password eye in a 44 px target", async ({ page }) => {
    await page.setViewportSize(PHONE);
    await page.goto("/ingresar");
    await settled(page);
    const size = await page.evaluate(() => {
      const rect = (selector: string) => {
        const element = document.querySelector<HTMLElement>(selector);
        if (!element) return null;
        const { width, height } = element.getBoundingClientRect();
        return { width, height };
      };
      return {
        email: rect('input[type="email"]'),
        password: rect('input[type="password"]'),
        submit: rect("form button[type=submit]"),
      };
    });
    expect(Math.round(size.email!.height)).toBe(44);
    expect(Math.round(size.password!.height)).toBe(44);
    expect(Math.round(size.submit!.height)).toBe(48);
    const autocomplete = await page.evaluate(() => [
      document.querySelector('input[type="email"]')?.getAttribute("autocomplete"),
      document.querySelector('input[type="password"]')?.getAttribute("autocomplete"),
    ]);
    expect(autocomplete).toEqual(["email", "current-password"]);
  });

  for (const width of WIDTHS) {
    for (const scheme of ["light", "dark"] as const) {
      test(`is intact at ${width} px in the ${scheme} theme`, async ({ page }) => {
        await page.setViewportSize({ width, height: 851 });
        await page.emulateMedia({ colorScheme: scheme });
        await page.goto("/ingresar");
        await settled(page);
        const overflow = await overflows(page);
        expect(overflow.scrollWidth, overflow.wide.join(" | ")).toBeLessThanOrEqual(overflow.viewport);
        const results = await new AxeBuilder({ page }).analyze();
        expect(results.violations).toEqual([]);
      });
    }
  }
});

test.describe("the Filtros | Parámetros sheet on a phone", () => {
  test("is full screen with a sticky footer that never covers the last control", async ({ page }) => {
    await page.setViewportSize(PHONE);
    await openReport(page);
    await page.getByRole("button", { name: /^Parámetros/ }).click();
    const sheet = page.getByTestId("report-sheet");
    await expect(sheet).toBeVisible();
    await settled(page);

    const geometry = await page.evaluate(() => {
      const panel = document.querySelector<HTMLElement>('[data-testid="report-sheet"]')!;
      const footer = panel.lastElementChild as HTMLElement;
      const body = panel.querySelector<HTMLElement>('[role="tabpanel"]')!;
      const panelRect = panel.getBoundingClientRect();
      const footerRect = footer.getBoundingClientRect();
      const last = [...body.querySelectorAll<HTMLElement>("label")].pop();
      last?.scrollIntoView({ block: "end" });
      const lastRect = last?.getBoundingClientRect() ?? null;
      const style = getComputedStyle(body);
      return {
        height: Math.round(panelRect.height),
        top: Math.round(panelRect.top),
        innerHeight: window.innerHeight,
        footerVisible: footerRect.bottom <= window.innerHeight + 1 && footerRect.height > 0,
        footerTop: Math.round(footerRect.top),
        bodyBottom: Math.round(body.getBoundingClientRect().bottom),
        lastBottom: lastRect ? Math.round(lastRect.bottom) : null,
        scrollPaddingBottom: parseFloat(style.scrollPaddingBottom),
      };
    });
    expect(geometry.height, "the sheet fills the viewport").toBe(geometry.innerHeight);
    expect(geometry.top).toBe(0);
    expect(geometry.footerVisible).toBe(true);
    // After scrolling the last control into view, the footer starts below it, not over it.
    expect(geometry.lastBottom).not.toBeNull();
    expect(geometry.lastBottom!).toBeLessThanOrEqual(geometry.footerTop + 1);
    // The body ends where the footer starts: the footer never overlays content.
    expect(geometry.bodyBottom).toBeLessThanOrEqual(geometry.footerTop + 1);
    // And a control scrolled into view stops above the footer.
    expect(geometry.scrollPaddingBottom).toBeGreaterThan(40);
  });

  test("has no drag handle and closes with the phone's back button", async ({ page }) => {
    await page.setViewportSize(PHONE);
    await openReport(page);
    await page.getByRole("button", { name: /^Filtros/ }).click();
    const sheet = page.getByTestId("report-sheet");
    await expect(sheet).toBeVisible();
    expect(await sheet.locator('[aria-hidden][class*="rounded-full"]').isVisible()).toBe(false);

    const url = page.url();
    await page.goBack();
    await expect(sheet).toHaveCount(0);
    // The back button closed the sheet rather than leaving the dashboard.
    expect(new URL(page.url()).pathname).toBe(new URL(url).pathname);
  });

  test("applies live, and Limpiar restores the defaults", async ({ page }) => {
    await page.setViewportSize(PHONE);
    await openReport(page);
    await page.getByRole("button", { name: /^Parámetros/ }).click();
    const panel = page.getByTestId("report-params-panel");
    await expect(panel).toBeVisible();
    const requests = { count: 0 };
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.endsWith("/data")) requests.count += 1;
    });
    // Period and comparison share one row: their boxes overlap vertically and sit side by side.
    const row = await page.evaluate(() => {
      const labels = [...document.querySelectorAll<HTMLLabelElement>('[data-testid="report-params-panel"] label')];
      const rect = (text: string) => {
        const label = labels.find((item) => item.textContent?.trim() === text);
        const control = label?.htmlFor ? document.getElementById(label.htmlFor) : null;
        const box = control?.getBoundingClientRect();
        return box ? { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width) } : null;
      };
      return { period: rect("Período"), compare: rect("Comparar con") };
    });
    expect(row.period).not.toBeNull();
    expect(row.compare).not.toBeNull();
    expect(row.period!.y).toBe(row.compare!.y);
    expect(row.compare!.x).toBeGreaterThan(row.period!.x + row.period!.w - 1);
    expect(row.period!.w).toBeGreaterThanOrEqual(160);

    const period = page.getByTestId("params-form").getByLabel("Período", { exact: true });
    const values = await period.evaluate((element) =>
      [...(element as HTMLSelectElement).options].map((option) => option.value),
    );
    const other = values.find((value) => value !== "custom");
    expect(other, "the report offers another period").toBeDefined();
    await period.selectOption(other!);
    await expect
      .poll(() => requests.count, { timeout: 10_000 })
      .toBeGreaterThan(0);
    await page.getByRole("button", { name: "Limpiar" }).click();
    await settled(page);
    // Limpiar puts the report's own period back.
    await expect(page).not.toHaveURL(/period=custom/);
  });

  test("keeps the palette and the theme in one scrollable chip row each", async ({ page }) => {
    await page.setViewportSize(PHONE);
    await openReport(page);
    await page.getByRole("button", { name: /^Parámetros/ }).click();
    const palette = page.getByTestId("palette-chips");
    await expect(palette).toBeVisible();
    const paletteRow = await palette.locator('[role="group"]').evaluate((element) => ({
      overflowX: getComputedStyle(element).overflowX,
      height: Math.round(element.getBoundingClientRect().height),
    }));
    expect(paletteRow.overflowX).toBe("auto");
    expect(paletteRow.height).toBeLessThan(80);
    await expect(page.getByTestId("theme-chips")).toHaveCount(0);
  });

  test("is a bottom sheet at 85 % on a tablet and the same side sheet on a desktop", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await openReport(page);
    await page.getByRole("button", { name: /^Filtros/ }).click();
    const sheet = page.getByTestId("report-sheet");
    const tablet = await sheet.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        height: Math.round(rect.height),
        ratio: rect.height / window.innerHeight,
        bottom: Math.round(rect.bottom),
        innerHeight: window.innerHeight,
      };
    });
    expect(tablet.ratio).toBeCloseTo(0.85, 1);
    expect(tablet.bottom).toBe(tablet.innerHeight);

    await page.setViewportSize({ width: 1280, height: 900 });
    await settled(page);
    const desktop = await sheet.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return { width: Math.round(rect.width), height: Math.round(rect.height), right: Math.round(rect.right) };
    });
    expect(desktop.height).toBe(900);
    expect(desktop.width).toBe(360);
    expect(desktop.right).toBe(1280);
  });

  for (const width of WIDTHS) {
    test(`is axe clean at ${width} px in both themes`, async ({ page }) => {
      await page.setViewportSize({ width, height: 851 });
      await openReport(page);
      await page.getByRole("button", { name: /^Parámetros/ }).click();
      await expect(page.getByTestId("report-params-panel")).toBeVisible();
      await setScheme(page, "light");
      let results = await new AxeBuilder({ page }).include('[data-testid="report-sheet"]').analyze();
      expect(results.violations).toEqual([]);
      await setScheme(page, "dark");
      results = await new AxeBuilder({ page }).include('[data-testid="report-sheet"]').analyze();
      expect(results.violations).toEqual([]);
      await setScheme(page, "light");
    });
  }
});

test.describe("the rest of the shell on a phone", () => {
  for (const route of ["/", "/ingresar", "/proyectos", `/r/ventas?${SEEDED}`]) {
    test(`has no horizontal scroll at 360 px on ${route}`, async ({ page }) => {
      await page.setViewportSize(FLAT_PHONE);
      if (route !== "/ingresar") await signIn(page);
      await page.goto(route);
      await settled(page);
      const overflow = await overflows(page);
      expect(overflow.scrollWidth, overflow.wide.join(" | ")).toBeLessThanOrEqual(overflow.viewport);
    });
  }

  test("hides the breadcrumb under 480 px and keeps the report actions reachable", async ({ page }) => {
    await page.setViewportSize(FLAT_PHONE);
    await openReport(page);
    const trail = page.locator("nav[aria-label]").first();
    if (await trail.count()) expect(await trail.isVisible()).toBe(false);
    await expect(page.getByRole("button", { name: /^Filtros/ })).toBeVisible();
    const actions = await page.getByTestId("report-actions").evaluate((element) => {
      const buttons = [...element.querySelectorAll("button")];
      return buttons.map((button) => Math.round(button.getBoundingClientRect().height));
    });
    expect(actions.every((height) => height >= 44)).toBe(true);
  });
});
