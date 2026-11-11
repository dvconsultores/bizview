import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Feature 054. Google is simulated through the backend's test hook
// (`POST /api/testing/google-identity`, BIZVIEW_TEST_HOOKS=1 in backend.sh): the authorization URL
// is real — state, PKCE and the state cookie included — and only the token exchange is answered
// locally, so the callback under test is the one production runs.
const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
  const r = await page.request.post("/api/auth/reauth", {
    headers: FETCH,
    data: { password: SUPER.password },
  });
  expect(r.status()).toBe(204);
}

async function expectAccessible(page: Page, where: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" | ")).join(" ; ")}`),
  ).toEqual([]);
}

async function policy(page: Page, settings: Record<string, unknown>) {
  const r = await page.request.put("/api/admin/google", { headers: FETCH, data: settings });
  expect(r.ok(), await r.text()).toBeTruthy();
}

/** Walk the real start endpoint and come back to the callback with a code the hook answers. */
async function signInWithGoogle(page: Page, email: string, name = "Cuenta E2E") {
  const identity = await page.request.post("/api/testing/google-identity", {
    headers: FETCH,
    data: { email, name },
  });
  expect(identity.ok()).toBeTruthy();
  const start = await page.request.get("/api/auth/google/start", { maxRedirects: 0 });
  expect(start.status()).toBe(302);
  const state = new URL(start.headers()["location"]).searchParams.get("state");
  expect(state).toBeTruthy();
  await page.goto(`/api/auth/google/callback?code=e2e-code&state=${state}`);
}

const me = async (page: Page) =>
  (await (await page.request.get("/api/me")).json()) as {
    email: string;
    role: string;
    is_superuser: boolean;
  };

test("a Google account on an allowed domain is provisioned and keeps the role the admin sets", async ({ page }, info) => {
  const email = `google-${info.project.name}-${Date.now()}@empresa.com`;
  await signIn(page);

  await policy(page, {
    allowed_domains: ["empresa.com"],
    auto_provision: true,
    default_role: "user",
    default_access: { mode: "all_public" },
    apply_rules_to_existing: false,
  });

  await signInWithGoogle(page, email);
  await expect(page).not.toHaveURL(/ingresar/);
  const provisioned = await me(page);
  expect(provisioned.email).toBe(email);
  expect(provisioned.role).toBe("user");
  expect(provisioned.is_superuser).toBe(false);

  // The default access is real: the account sees the public dashboards it was given.
  const granted = (await (await page.request.get("/api/dashboards")).json()) as {
    items: { code: string; name: string }[];
  };
  expect(granted.items.length).toBeGreaterThan(0);
  await page.goto("/tableros");
  await expect(page.getByRole("link", { name: granted.items[0].name }).first()).toBeVisible();

  // An administrator raises the role; the next sign-in keeps it (no rule rewrites an existing user).
  await page.context().clearCookies();
  await signIn(page);
  const list = (await (await page.request.get(`/api/admin/users?q=${encodeURIComponent(email)}`))
    .json()) as { items: { id: number; email: string }[] };
  const target = list.items.find((u) => u.email === email);
  expect(target).toBeTruthy();
  const patched = await page.request.patch(`/api/admin/users/${target!.id}`, {
    headers: FETCH,
    data: { role: "admin" },
  });
  expect(patched.ok()).toBeTruthy();

  await page.context().clearCookies();
  await signInWithGoogle(page, email);
  const again = await me(page);
  expect(again.role).toBe("admin");

  // The audit log names the provisioning and the admin's change, never a credential. Reading it is
  // the superuser's business, so the last sign-in of this flow is the administrator's.
  await page.context().clearCookies();
  await signIn(page);
  const audit = (await (await page.request.get("/api/admin/audit?kind=google_user_provisioned"))
    .json()) as { items: { target: { email: string } | null }[] };
  expect(audit.items.some((e) => e.target?.email === email)).toBe(true);
});

test("a foreign domain is refused with the generic message and the reason stays in the audit", async ({ page }, info) => {
  await signIn(page);
  await policy(page, {
    allowed_domains: ["empresa.com"],
    auto_provision: true,
    default_role: "user",
    default_access: { mode: "none" },
    apply_rules_to_existing: false,
  });

  const foreign = `ajena-${info.project.name}-${Date.now()}@otro-dominio.test`;
  await signInWithGoogle(page, foreign);
  // The page never says why: same sentence as an unknown account or a deactivated one.
  await expect(page).toHaveURL(/google_error=domain_not_allowed/);
  await expect(page.getByRole("alert").first()).toContainText(
    "No se pudo iniciar sesión con Google. Inténtalo de nuevo.",
  );
  await expectAccessible(page, "ingreso");

  await page.context().clearCookies();
  await signIn(page);
  const refused = (await (await page.request.get("/api/admin/audit?kind=google_sign_in_refused"))
    .json()) as { items: { detail: { reason?: string } | null }[] };
  expect(refused.items.some((e) => e.detail?.reason === "domain_not_allowed")).toBe(true);
});

test("an administrator creates a Google-only user and the granted dashboards are there", async ({ page }, info) => {
  const email = `solo-${info.project.name}-${Date.now()}@empresa.com`;
  await signIn(page);
  await page.goto("/admin/usuarios/nuevo");

  await page.getByLabel("Nombre completo").fill("Cuenta Google");
  await page.getByLabel("Correo electrónico").fill(email);
  // Convergence 054b: Google is enabled, so no password is the default, and the temporary
  // password field is not offered.
  const noPassword = page.getByRole("switch", { name: "Sin contraseña (solo Google / Telegram)" });
  await expect(noPassword).toHaveAttribute("aria-checked", "true");
  await expect(page.getByLabel("Contraseña temporal")).toHaveCount(0);
  await page.getByRole("button", { name: "Crear usuario" }).click();

  const created = page.getByRole("region", { name: "Usuario creado." });
  await expect(created).toContainText("No se creó contraseña");
  await created.getByRole("button", { name: "Ver usuario" }).click();
  await expect(page.getByText("Solo Google")).toBeVisible();
  await expect(page.getByText("Clave temporal")).toHaveCount(0);
  await expect(page).toHaveURL(/\/admin\/usuarios\/\d+$/);
  const id = Number(page.url().split("/").pop());

  // Grant one dashboard through the existing access endpoint.
  const detail = (await (await page.request.get(`/api/admin/users/${id}`)).json()) as {
    dashboards: { code: string; name: string; status: string }[];
  };
  const granted = detail.dashboards.find((d) => d.status === "available");
  expect(granted).toBeTruthy();
  const put = await page.request.put(`/api/admin/users/${id}/dashboards`, {
    headers: FETCH,
    data: { codes: [granted!.code] },
  });
  expect(put.ok(), await put.text()).toBeTruthy();

  // From now on the account signs in with Google and lands in the app, not on /cambiar-clave.
  await page.context().clearCookies();
  await signInWithGoogle(page, email);
  await expect(page).not.toHaveURL(/ingresar|cambiar-clave/);
  await page.goto("/tableros");
  await expect(page.getByRole("link", { name: granted!.name }).first()).toBeVisible();
});

test("an administrator removes a temporary password so the account is Google-only", async ({ page }, info) => {
  const email = `sin-clave-${info.project.name}-${Date.now()}@empresa.com`;
  await signIn(page);

  const made = await page.request.post("/api/admin/users", {
    headers: FETCH,
    data: { email, full_name: "Sin Clave", role: "user", temporary_password: "Temporal-pass-91" },
  });
  expect(made.status()).toBe(201);
  const id = ((await made.json()) as { id: number }).id;

  await page.goto(`/admin/usuarios/${id}`);
  await expect(page.getByText("Clave temporal")).toBeVisible();
  await page.getByRole("button", { name: "Quitar contraseña" }).click();
  const confirm = page.getByRole("region", { name: "Quitar contraseña" });
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Quitar contraseña" }).click();
  await expect(page.getByText("Contraseña eliminada.", { exact: false })).toBeVisible();
  await expect(page.getByText("Solo Google")).toBeVisible();
  await expect(page.getByText("Clave temporal")).toHaveCount(0);

  await page.context().clearCookies();
  await signInWithGoogle(page, email);
  await expect(page).not.toHaveURL(/ingresar|cambiar-clave/);
  expect((await me(page)).email).toBe(email);
});

test("the Seguridad card edits the domains and the rules, and the sheet is accessible", async ({ page }) => {
  await signIn(page);
  await page.goto("/admin/seguridad");
  const card = page.getByRole("region", { name: "Ingreso con Google" });
  await expect(card).toBeVisible();
  await expectAccessible(page, "seguridad");

  // A domain the deployment never had becomes configuration.
  await card.getByLabel("Dominios permitidos").fill("acme.test");
  await card.getByRole("button", { name: "Agregar", exact: true }).click();
  await expect(card.getByText("acme.test")).toBeVisible();
  await card.getByRole("button", { name: "Guardar" }).first().click();
  await expect(page.getByText("Política de Google guardada.")).toBeVisible();

  const saved = (await (await page.request.get("/api/admin/google")).json()) as {
    settings: { allowed_domains: string[]; domains_from_env: boolean };
  };
  expect(saved.settings.allowed_domains).toContain("acme.test");
  expect(saved.settings.domains_from_env).toBe(false);

  // A rule: the group condition is announced as coming soon, and the rule saves as an email match.
  await card.getByRole("button", { name: "Agregar regla" }).click();
  const editor = card.locator("form");
  await expect(editor.locator("option[value=group]")).toBeDisabled();
  await editor.getByLabel("Condición").selectOption("email");
  await editor.getByLabel("Correos, uno por línea").fill("ana@acme.test");
  await editor.getByRole("button", { name: "Guardar" }).click();
  await expect(card.getByText("ana@acme.test")).toBeVisible();
  await expect(page.getByText("Regla creada.")).toBeVisible();
});
