import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type BrowserContext } from "@playwright/test";
import { totp } from "./totp";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };

async function signIn(page: Page, email = SUPER.email, password = SUPER.password) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function signOut(page: Page) {
  await page.goto("/perfil");
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/ingresar/);
}

async function expectAccessible(page: Page, where: string) {
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

const settled = (page: Page) => page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r()))));
const theme = (page: Page) =>
  page.evaluate(() => document.documentElement.dataset.theme);

async function expectView(page: Page, title: string) {
  const view = page.locator("main").getByRole("region", { name: title, exact: true });
  await expect(view).toBeVisible();
  await expect(page.locator("[role=dialog], [aria-modal]")).toHaveCount(0);
  await expect(page.locator("main > div").first()).toBeHidden();
  return view;
}

async function changePassword(page: Page, temp: string, final: string) {
  await page.getByLabel("Contraseña temporal").fill(temp);
  await page.getByLabel("Nueva contraseña", { exact: true }).fill(final);
  await page.getByLabel("Confirmar nueva contraseña").fill(final);
  await page.getByRole("button", { name: "Cambiar contraseña" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bienvenido de nuevo, ");
}

async function reauthWith(page: Page, password: string) {
  const res = await page.request.post("/api/auth/reauth", {
    headers: FETCH,
    data: { password },
  });
  expect(res.status()).toBe(204);
}

async function expectAccessibleBothThemes(page: Page, where: string) {
  await expectAccessible(page, `${where} light`);
  await page.emulateMedia({ colorScheme: "dark" });
  await expect.poll(() => theme(page)).toBe("dark");
  await settled(page);
  await expectAccessible(page, `${where} dark`);
  await page.emulateMedia({ colorScheme: "light" });
  await expect.poll(() => theme(page)).toBe("light");
  await settled(page);
}

test.describe("views instead of modals", () => {
  test("font and wide layout", async ({ page, browser }, info) => {
    const font = page.waitForResponse(
      (r) =>
        r.url().startsWith("http://localhost:4173/") &&
        /\/plus-jakarta-sans-[^/]*\.woff2(\?|$)/.test(r.url()),
    );
    await page.goto("/ingresar");
    const fontResponse = await font;
    expect(fontResponse.ok()).toBeTruthy();
    const fontFamily = await page.evaluate(
      () => getComputedStyle(document.body).fontFamily,
    );
    expect(fontFamily).toMatch(/^"?Plus Jakarta Sans"?\s*,/);

    await signIn(page);
    for (const route of ["/admin/usuarios", "/admin/usuarios/nuevo"]) {
      await page.goto(route);
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    }

    const desktopContext = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
    });
    let source: { id: number } | undefined;
    try {
      const desktopPage = await desktopContext.newPage();
      await signIn(desktopPage);
      await reauthWith(desktopPage, SUPER.password);

      const sourceRes = await desktopPage.request.post("/api/sources", {
        headers: FETCH,
        data: {
          name: `${info.project.name}-${Date.now()}-ancho`,
          kind: "postgresql",
          settings: { host: "203.0.113.9", database: "d", username: "u" },
          secrets: { password: "Fake-pass-123" },
        },
      });
      expect(sourceRes.status()).toBe(201);
      source = (await sourceRes.json()) as { id: number };

      const meRes = await desktopPage.request.get("/api/me");
      expect(meRes.ok()).toBeTruthy();
      const me = (await meRes.json()) as { id: number };
      const minWidth = 0.85 * (1920 - 256);
      const routes = [
        "/admin",
        "/admin/usuarios",
        "/admin/usuarios/nuevo",
        `/admin/usuarios/${me.id}`,
        "/admin/auditoria",
        "/admin/ia",
        "/admin/fuentes",
        "/admin/fuentes/nueva",
        `/admin/fuentes/${source.id}`,
        "/admin/seguridad",
        "/admin/espacio",
        "/admin/integraciones",
        "/admin/tokens",
        "/perfil",
      ];
      for (const route of routes) {
        await desktopPage.goto(route);
        await expect(desktopPage.locator("[aria-busy=true]")).toHaveCount(0);
        await expect(desktopPage.getByRole("heading", { level: 1 }).first()).toBeVisible();
        const main = desktopPage.locator("main");
        const box = await main.evaluate((el) => ({
          clientWidth: el.clientWidth,
          paddingLeft: getComputedStyle(el).paddingLeft,
          paddingRight: getComputedStyle(el).paddingRight,
        }));
        const contentWidth =
          box.clientWidth - parseFloat(box.paddingLeft) - parseFloat(box.paddingRight);
        expect(contentWidth, route).toBeGreaterThanOrEqual(minWidth);
        const pageWidth = await desktopPage.evaluate(() => {
          const el = document.querySelector("main > div:first-child > :first-child");
          return el ? el.getBoundingClientRect().width : 0;
        });
        expect(pageWidth, route).toBeGreaterThanOrEqual(minWidth);
      }
    } finally {
      try {
        if (source) {
          const del = await desktopContext.request.delete(`/api/sources/${source.id}`, {
            headers: FETCH,
          });
          expect.soft(del.status()).toBe(204);
        }
      } finally {
        await desktopContext.close();
      }
    }
  });

  test("Usuario creado is a view and the secret does not survive history", async ({
    page,
  }, info) => {
    const unique = `${info.project.name}-${Date.now()}`;
    await signIn(page);
    await page.goto("/admin/usuarios/nuevo");
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);

    const fullName = `${unique} Nuevo Usuario`;
    const email = `${unique}-created@example.com`;
    await page.getByLabel("Nombre completo").fill(fullName);
    await page.getByLabel("Correo electrónico").fill(email);
    const tempPassword = await page.getByLabel("Contraseña temporal").inputValue();
    await page.getByRole("button", { name: "Crear usuario" }).click();

    const view = await expectView(page, "Usuario creado.");
    await expect(view.getByText(tempPassword, { exact: true })).toBeVisible();
    await expect
      .poll(async () =>
        page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        ),
      )
      .toBeLessThanOrEqual(0);
    await expectAccessibleBothThemes(page, "Usuario creado");

    await page.goBack();
    await expect
      .poll(() => page.locator('main [role="region"]').count())
      .toBe(0);
    await page.waitForURL(/\/admin\/usuarios\/\d+$/);
    await page.goForward();
    await page.reload();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.content()).not.toContain(tempPassword);
    await expect(page.getByText(tempPassword, { exact: true })).toHaveCount(0);
  });

  test("user detail confirmations", async ({ page }, info) => {
    const unique = `${info.project.name}-${Date.now()}`;
    const email = `${unique}-detail@example.com`;
    const fullName = `${unique} Detalle Usuario`;

    await signIn(page);
    const createRes = await page.request.post("/api/admin/users", {
      headers: FETCH,
      data: {
        email,
        full_name: fullName,
        role: "user",
        temporary_password: "Temporal-pass-88",
      },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()) as { id: number };
    const detailUrl = `/admin/usuarios/${created.id}`;

    await page.goto(detailUrl);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(fullName);
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);

    // a: back via view Volver button keeps user active
    await page.getByRole("button", { name: "Desactivar usuario" }).click();
    const deactivateView = await expectView(page, "Desactivar usuario");
    await expectAccessibleBothThemes(page, "Desactivar usuario");
    await deactivateView.getByRole("button", { name: "Volver" }).click();
    await expect(deactivateView).toHaveCount(0);
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    let detail = (await (
      await page.request.get(`/api/admin/users/${created.id}`)
    ).json()) as { user: { is_active: boolean } };
    expect(detail.user.is_active).toBe(true);

    // b: browser back closes view and keeps user active
    await page.getByRole("button", { name: "Desactivar usuario" }).click();
    await expectView(page, "Desactivar usuario");
    await page.goBack();
    await expect(
      page.locator('main [role="region"][aria-labelledby]'),
    ).toHaveCount(0);
    expect(new URL(page.url()).pathname).toContain(detailUrl);
    detail = (await (
      await page.request.get(`/api/admin/users/${created.id}`)
    ).json()) as { user: { is_active: boolean } };
    expect(detail.user.is_active).toBe(true);

    // c: Escape closes view
    await page.getByRole("button", { name: "Desactivar usuario" }).click();
    await expectView(page, "Desactivar usuario");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("region", { name: "Desactivar usuario" })).toHaveCount(0);

    // d: reset password view, focus, axe in light and dark
    await page.getByRole("button", { name: "Restablecer contraseña" }).click();
    const resetView = await expectView(page, "Restablecer contraseña");
    await expect(resetView.getByLabel("Contraseña temporal")).toBeFocused();
    await expectAccessibleBothThemes(page, "Restablecer contraseña");
    await resetView.getByRole("button", { name: "Cancelar" }).click();
    await expect(resetView).toHaveCount(0);
  });

  test("two-step views", async ({ page }, info) => {
    test.setTimeout(120_000);
    const unique = `${info.project.name}-${Date.now()}`;
    const email = `${unique}-mfa@example.com`;
    const fullName = `${unique} Mfa Usuario`;
    const tempPassword = "Temporal-pass-77";
    const finalPassword = "Final-pass-99";

    await signIn(page);
    const createRes = await page.request.post("/api/admin/users", {
      headers: FETCH,
      data: {
        email,
        full_name: fullName,
        role: "user",
        temporary_password: tempPassword,
      },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()) as { id: number };

    await signOut(page);
    await signIn(page, email, tempPassword);
    await changePassword(page, tempPassword, finalPassword);

    await reauthWith(page, finalPassword);
    const setupRes = await page.request.post("/api/me/mfa/setup", {
      headers: FETCH,
    });
    expect(setupRes.status()).toBe(200);
    const setup = (await setupRes.json()) as { secret: string };
    const enableRes = await page.request.post("/api/me/mfa/enable", {
      headers: FETCH,
      data: { code: totp(setup.secret) },
    });
    expect(enableRes.status()).toBe(200);

    await page.goto("/perfil");
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    await page
      .getByRole("button", { name: "Generar nuevos códigos de recuperación" })
      .click();
    const recoveryView = await expectView(
      page,
      "Guarda tus códigos de recuperación",
    );
    await expect(recoveryView.locator("ul li")).toHaveCount(10);
    await expectAccessibleBothThemes(page, "Recovery codes");
    await recoveryView.getByRole("button", { name: "Ya los guardé" }).click();
    await expect(recoveryView).toHaveCount(0);

    await page.getByRole("button", { name: "Desactivar", exact: true }).click();
    const disableView = await expectView(
      page,
      "Desactivar la verificación en dos pasos",
    );
    await expectAccessibleBothThemes(page, "Desactivar la verificación en dos pasos");
    await disableView.getByRole("button", { name: "Cancelar" }).click();
    await expect(disableView).toHaveCount(0);

    await signOut(page);
    await signIn(page);
    await page.goto(`/admin/usuarios/${created.id}`);
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    await page.getByRole("button", { name: "Restablecer doble factor" }).click();
    const resetMfaView = await expectView(page, "Restablecer doble factor");
    await expectAccessibleBothThemes(page, "Restablecer doble factor");
    await resetMfaView.getByRole("button", { name: "Cancelar" }).click();
    await expect(resetMfaView).toHaveCount(0);
  });

  test("source delete and workspace rollback views", async ({ page }, info) => {
    const unique = `${info.project.name}-${Date.now()}`;
    await signIn(page);
    await reauthWith(page, SUPER.password);

    const sourceName = `${unique}-fuente`;
    const createRes = await page.request.post("/api/sources", {
      headers: FETCH,
      data: {
        name: sourceName,
        kind: "postgresql",
        settings: { host: "203.0.113.9", database: "d", username: "u" },
        secrets: { password: "Fake-pass-123" },
      },
    });
    expect(createRes.status()).toBe(201);
    const source = (await createRes.json()) as { id: number };

    try {
      await page.goto(`/admin/fuentes/${source.id}`);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(sourceName);
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
      await page.getByRole("button", { name: "Eliminar fuente" }).click();
      const deleteView = await expectView(page, "Eliminar fuente");
      await expectAccessibleBothThemes(page, "Eliminar fuente");
      await deleteView.getByRole("button", { name: "Cancelar" }).click();
      await expect(deleteView).toHaveCount(0);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    } finally {
      const deleteRes = await page.request.delete(`/api/sources/${source.id}`, {
        headers: FETCH,
      });
      expect(deleteRes.status()).toBe(204);
    }

    const workspaceRes = await page.request.get("/api/workspace");
    expect(workspaceRes.ok()).toBeTruthy();
    const workspace = (await workspaceRes.json()) as {
      previous: unknown | null;
    };
    if (!workspace.previous) {
      const applyRes = await page.request.post("/api/workspace/apply", {
        headers: FETCH,
      });
      expect(applyRes.status()).toBe(200);
    }
    const wsRes = await page.request.get("/api/workspace");
    expect(wsRes.ok()).toBeTruthy();
    const ws = (await wsRes.json()) as {
      previous: unknown | null;
    };
    expect(ws.previous).not.toBeNull();
    await page.goto("/admin/espacio");
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    await page
      .getByRole("button", { name: "Volver a la versión anterior" })
      .click();
    const rollbackView = await expectView(
      page,
      "¿Volver a la versión anterior?",
    );
    await expectAccessibleBothThemes(page, "¿Volver a la versión anterior?");
    await rollbackView.getByRole("button", { name: "Cancelar" }).click();
    await expect(rollbackView).toHaveCount(0);
  });

  test("step-up from the delete-source confirmation", async ({
    page,
    browser,
  }, info) => {
    const unique = `${info.project.name}-${Date.now()}`;
    const sourceName = `${unique}-paso`;
    const admin = await browser.newContext();
    let adminPage: Page | undefined;
    let source: { id: number } | undefined;
    const deleteStatuses: number[] = [];

    try {
      const adminTab = await admin.newPage();
      adminPage = adminTab;
      await signIn(page);
      await signIn(adminTab);
      await reauthWith(adminTab, SUPER.password);

      const createRes = await adminTab.request.post("/api/sources", {
        headers: FETCH,
        data: {
          name: sourceName,
          kind: "postgresql",
          settings: { host: "203.0.113.9", database: "d", username: "u" },
          secrets: { password: "Fake-pass-123" },
        },
      });
      expect(createRes.status()).toBe(201);
      source = (await createRes.json()) as { id: number };
      const sourceId = source.id;

      page.on("response", (response) => {
        if (
          response.request().method() === "DELETE" &&
          response.url().includes(`/api/sources/${sourceId}`)
        ) {
          deleteStatuses.push(response.status());
        }
      });

      await page.goto(`/admin/fuentes/${sourceId}`);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(sourceName);
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
      await page.getByRole("button", { name: "Eliminar fuente" }).click();
      const deleteView = await expectView(page, "Eliminar fuente");
      await deleteView.getByRole("button", { name: "Eliminar fuente" }).click();
      const stepUp = await expectView(page, "Confirma tu contraseña");
      await stepUp.getByRole("button", { name: "Cancelar" }).click();
      await expect(stepUp).toHaveCount(0);
      const deleteViewAgain = page.locator("main").getByRole("region", {
        name: "Eliminar fuente",
        exact: true,
      });
      await expect(deleteViewAgain).toBeVisible();
      await expect(deleteViewAgain.locator("[role=alert]")).toBeVisible();
      const checkRes = await adminTab.request.get(`/api/sources/${sourceId}`);
      expect(checkRes.status()).toBe(200);
      expect(deleteStatuses.filter((s) => s === 204)).toHaveLength(0);

      await deleteViewAgain.getByRole("button", { name: "Eliminar fuente" }).click();
      const stepUpAgain = await expectView(page, "Confirma tu contraseña");
      await stepUpAgain
        .getByLabel("Contraseña", { exact: true })
        .fill(SUPER.password);
      await stepUpAgain.getByRole("button", { name: "Confirmar" }).click();
      await expect(stepUpAgain).toHaveCount(0);
      await expect(page).toHaveURL(/\/admin\/fuentes$/);
      await expect
        .poll(async () => {
          const res = await adminTab.request.get(`/api/sources/${sourceId}`);
          return res.status();
        })
        .toBe(404);
      expect(deleteStatuses.filter((s) => s === 204)).toHaveLength(1);
    } finally {
      if (source && adminPage) {
        const getRes = await adminPage.request.get(`/api/sources/${source.id}`);
        if (getRes.status() !== 404) {
          await adminPage.request.delete(`/api/sources/${source.id}`, {
            headers: FETCH,
          });
        }
      }
      await admin.close();
    }
  });

  test("telegram unlink and reactivate confirmation views", async ({
    page,
    browser,
  }, info) => {
    test.setTimeout(120_000);
    const unique = `${info.project.name}-${Date.now()}`;
    const email = `${unique}-telegram@example.com`;
    const fullName = `${unique} Telegram Usuario`;
    const tempPassword = "Temporal-pass-66";
    const finalPassword = "Final-pass-66";
    const TG_FROM = { id: 7301, first_name: "Eva", last_name: "Vista", username: "eva_vista" };
    let updateCounter = 0;

    await signIn(page);
    await reauthWith(page, SUPER.password);

    const createRes = await page.request.post("/api/admin/users", {
      headers: FETCH,
      data: {
        email,
        full_name: fullName,
        role: "user",
        temporary_password: tempPassword,
      },
    });
    expect(createRes.status()).toBe(201);
    const created = (await createRes.json()) as { id: number };

    let userCtx: BrowserContext | undefined;
    try {
      const resetRes = await page.request.post("/api/test/telegram/reset", {
        headers: FETCH,
      });
      expect(resetRes.ok()).toBeTruthy();
      const configRes = await page.request.put("/api/admin/telegram", {
        headers: FETCH,
        data: { bot_username: "BizviewE2eBot", token: "123456789:AAE2E-test-credential-0001" },
      });
      expect(configRes.ok()).toBeTruthy();
      const checkOkRes = await page.request.post("/api/test/telegram/check-ok", {
        headers: FETCH,
      });
      expect(checkOkRes.ok()).toBeTruthy();
      const enableRes = await page.request.post("/api/admin/telegram/enabled", {
        headers: FETCH,
        data: { enabled: true },
      });
      expect(enableRes.ok()).toBeTruthy();

      userCtx = await browser.newContext();
      const userPage = await userCtx.newPage();
      await signIn(userPage, email, tempPassword);
      const pwRes = await userPage.request.post("/api/me/password", {
        headers: FETCH,
        data: { current_password: tempPassword, new_password: finalPassword },
      });
      expect(pwRes.status()).toBe(204);
      await reauthWith(userPage, finalPassword);
      const linkRes = await userPage.request.post("/api/me/telegram/link", {
        headers: FETCH,
      });
      expect(linkRes.ok()).toBeTruthy();
      const linkData = (await linkRes.json()) as { deep_link: string };
      const token = linkData.deep_link.split("start=")[1];

      updateCounter++;
      const startUpdateRes = await page.request.post("/api/test/telegram/update", {
        headers: FETCH,
        data: {
          update_id: updateCounter,
          message: {
            message_id: 1,
            from: TG_FROM,
            chat: { id: 7301, type: "private" },
            date: 0,
            text: `/start ${token}`,
          },
        },
      });
      expect(startUpdateRes.ok()).toBeTruthy();
      const sentRes = await page.request.get("/api/test/telegram/sent");
      expect(sentRes.ok()).toBeTruthy();
      const sent = (await sentRes.json()) as {
        reply_markup?: { inline_keyboard: { callback_data: string }[][] };
      }[];
      const messageWithKeyboard = sent
        .slice()
        .reverse()
        .find((m) => m.reply_markup?.inline_keyboard);
      expect(messageWithKeyboard).toBeTruthy();
      const callbackData = messageWithKeyboard!.reply_markup!.inline_keyboard
        .flat()
        .map((b) => b.callback_data)
        .find((cd) => cd.startsWith("ok:"))!;
      expect(callbackData).toBeTruthy();

      updateCounter++;
      const cbUpdateRes = await page.request.post("/api/test/telegram/update", {
        headers: FETCH,
        data: {
          update_id: updateCounter,
          callback_query: {
            id: `cb${updateCounter}`,
            from: TG_FROM,
            message: {
              message_id: 1,
              chat: { id: 7301, type: "private" },
              date: 0,
              text: "",
            },
            data: callbackData,
          },
        },
      });
      expect(cbUpdateRes.ok()).toBeTruthy();

      await expect
        .poll(async () => {
          const res = await page.request.get(`/api/admin/users/${created.id}`);
          expect(res.ok()).toBeTruthy();
          const data = (await res.json()) as { telegram_linked: boolean };
          return data.telegram_linked;
        })
        .toBe(true);

      await page.goto(`/admin/usuarios/${created.id}`);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(fullName);
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);

      await page.getByRole("button", { name: "Quitar vínculo de Telegram" }).click();
      const unlinkView = await expectView(page, "Quitar vínculo de Telegram");
      await expectAccessibleBothThemes(page, "Quitar vínculo de Telegram");
      await page.goBack();
      await expect(unlinkView).toHaveCount(0);
      expect(new URL(page.url()).pathname).toContain(`/admin/usuarios/${created.id}`);
      let detailRes = await page.request.get(`/api/admin/users/${created.id}`);
      let detailData = (await detailRes.json()) as {
        telegram_linked: boolean;
        user: { is_active: boolean };
      };
      expect(detailData.telegram_linked).toBe(true);

      const deactivateRes = await page.request.patch(`/api/admin/users/${created.id}`, {
        headers: FETCH,
        data: { is_active: false },
      });
      expect(deactivateRes.ok()).toBeTruthy();
      await page.reload();
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
      await page.getByRole("button", { name: "Reactivar usuario" }).click();
      const reactivateView = await expectView(page, "Reactivar usuario");
      await expectAccessibleBothThemes(page, "Reactivar usuario");
      await page.goBack();
      await expect(reactivateView).toHaveCount(0);
      detailRes = await page.request.get(`/api/admin/users/${created.id}`);
      detailData = (await detailRes.json()) as {
        telegram_linked: boolean;
        user: { is_active: boolean };
      };
      expect(detailData.user.is_active).toBe(false);

      await page.getByRole("button", { name: "Reactivar usuario" }).click();
      const reactivateViewAgain = await expectView(page, "Reactivar usuario");
      await reactivateViewAgain.getByRole("button", { name: "Cancelar" }).click();
      await expect(reactivateViewAgain).toHaveCount(0);
    } finally {
      await page.request.patch(`/api/admin/users/${created.id}`, {
        headers: FETCH,
        data: { is_active: true },
      });
      await page.request.post("/api/test/telegram/reset", {
        headers: FETCH,
      });
      await userCtx?.close();
    }
  });

  test("step-up keeps the page and creates exactly one token", async ({
    page,
  }, info) => {
    const unique = `${info.project.name}-${Date.now()}`;
    const tokenName = `${unique}-token`;
    await signIn(page);

    const beforeRes = await page.request.get("/api/tokens");
    expect(beforeRes.ok()).toBeTruthy();
    const beforeTokens = (await beforeRes.json()) as {
      items: { id: number; name: string }[];
    };
    const beforeCount = beforeTokens.items.length;

    await page.goto("/admin/tokens");
    await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
    const nameInput = page.getByLabel("Nombre", { exact: true });
    await nameInput.fill(tokenName);
    await page.getByRole("button", { name: "Crear token" }).click();

    const stepUpView = await expectView(page, "Confirma tu contraseña");
    await stepUpView.getByRole("button", { name: "Cancelar" }).click();
    await expect(stepUpView).toHaveCount(0);
    await expect(nameInput).toHaveValue(tokenName);
    const afterCancelRes = await page.request.get("/api/tokens");
    const afterCancelTokens = (await afterCancelRes.json()) as {
      items: { id: number; name: string }[];
    };
    expect(afterCancelTokens.items).toHaveLength(beforeCount);

    await page.getByRole("button", { name: "Crear token" }).click();
    const confirmView = await expectView(page, "Confirma tu contraseña");
    await confirmView
      .getByLabel("Contraseña", { exact: true })
      .fill(SUPER.password);
    await confirmView.getByRole("button", { name: "Confirmar" }).click();
    await expect(confirmView).toHaveCount(0);
    await expect(
      page.getByText(
        "Copia el token ahora: no se volverá a mostrar.",
      ),
    ).toBeVisible();

    let matchedTokens: { id: number; name: string }[] = [];
    await expect
      .poll(async () => {
        const res = await page.request.get("/api/tokens");
        const tokens = (await res.json()) as {
          items: { id: number; name: string }[];
        };
        matchedTokens = tokens.items.filter((t) => t.name === tokenName);
        return {
          count: tokens.items.length,
          matched: matchedTokens.length,
        };
      })
      .toEqual({ count: beforeCount + 1, matched: 1 });
    await expect(nameInput).toHaveValue("");

    const cleanupRes = await page.request.delete(
      `/api/tokens/${matchedTokens[0].id}`,
      { headers: FETCH },
    );
    expect(cleanupRes.status()).toBe(204);
  });
});
