// Feature 017 SC-003/SC-004 on the 020 project and 021 commands: from an empty installation the
// agent implements an integration spec and a report spec with /speckit-implement (scripted fake
// provider), the user applies the project, the worker builds ds_<integration> and a normal user
// opens the dashboard and its PDF. The test hooks stash the seeded workspace versions first.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import draft from "./fixtures/agent-draft.json" with { type: "json" };

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const LEGACY: Record<string, string> = draft;
const INTEGRATION = "001-facturas-agente";
const REPORT = "002-facturas-agente";

/** The 017 fixture in the v2 project layout (020): numbered spec folders with a **Tipo** line. */
function v2(): Record<string, string> {
  const folders: Array<[string, string, string]> = [
    ["specs/integrations/001-facturas-agente", `specs/${INTEGRATION}`, "integracion"],
    ["specs/reports/001-facturas-agente", `specs/${REPORT}`, "reporte"],
  ];
  const out: Record<string, string> = {};
  for (const [path, original] of Object.entries(LEGACY)) {
    if (path === "bizview.yaml") continue;
    let target = path;
    let text = original;
    for (const [old, now, kind] of folders) {
      text = text.split(old).join(now);
      if (path.startsWith(`${old}/`)) {
        target = now + path.slice(old.length);
        if (target.endsWith("/spec.md")) text = text.replace(/\n/, `\n\n**Tipo**: ${kind}\n`);
      }
    }
    out[target] = text;
  }
  return out;
}

interface RunResult {
  ok: boolean;
  status: string;
  message: string;
  schema: string;
  tables: Record<string, string[]>;
  primary_keys: Record<string, string[]>;
  schedules: string[][];
}

async function signIn(page: Page, email = SUPER.email, password = SUPER.password) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function check(page: Page) {
  // WebKit keeps stale computed styles for a frame after a view change.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
}

async function hook<T>(page: Page, path: string, data?: Record<string, unknown>): Promise<T> {
  const r = await page.request.post(path, { headers: FETCH, data });
  expect(r.ok(), `${path} should succeed`).toBe(true);
  return (await r.json()) as T;
}

async function openChat(page: Page, slug: string, sid: number) {
  await page.goto(`/proyectos/${slug}?chat=${sid}`);
  const chatTab = page.getByRole("tab", { name: "Chat" });
  // Narrow layouts show tabs (Chat must be picked); wide ones show the composer at once.
  await expect(chatTab.or(page.getByLabel("Mensaje para el asistente")).first()).toBeVisible();
  if (await chatTab.isVisible()) await chatTab.click();
  return page.getByLabel("Mensaje para el asistente");
}

async function setSpec(page: Page, sid: number, folder: string) {
  const r = await page.request.patch(`/api/assistant/sessions/${sid}`, {
    headers: FETCH, data: { current_spec: folder },
  });
  expect(r.ok()).toBe(true);
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/api/test/assistant/reset", { headers: FETCH });
  const stashed = await hook<{ ok: boolean; stashed: number[] }>(page, "/api/test/workspace/stash");
  expect(stashed.ok).toBe(true);
});

// The rest of the suite expects the seeded workspace and the AI off.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await hook<{ ok: boolean; restored: number[] }>(page, "/api/test/workspace/restore");
  await page.request.post("/api/test/assistant/reset", { headers: FETCH });
});

test("empty installation → /speckit-implement ×2 → apply → ds_facturas_agente + dashboard + PDF", async ({ page, browser }, info) => {
  test.skip(info.project.name.endsWith("-320"), "flow checked once per engine");
  test.setTimeout(300_000);
  const files = v2();
  const query = "integrations/facturas-agente/queries/facturas.sql";
  const scripted = await page.request.post("/api/test/assistant/script", {
    headers: FETCH,
    data: {
      steps: [
        // Run 1: the integration spec.
        { text: "", tool_calls: [{ id: "a1", name: "update_notes", args: { goal: "Tablero de facturas por día y estado, cada hora, con PDF", step: "Integración" } }] },
        { text: "", tool_calls: [{ id: "a2", name: "get_authoring_guide", args: { topic: "example" } }] },
        { text: "", tool_calls: [{ id: "a3", name: "list_sources", args: {} }] },
        { text: "", tool_calls: [{ id: "a4", name: "describe_source", args: { name: "Origen e2e" } }] },
        { text: "", tool_calls: [{ id: "a5", name: "profile_source", args: { name: "Origen e2e", table: "app_test_e2e.origin_invoices" } }] },
        { text: "", tool_calls: [{ id: "a6", name: "edit_draft", args: { ops: [
          { op: "write", path: "integrations/facturas-agente/integration.yaml", content: files["integrations/facturas-agente/integration.yaml"] },
          { op: "write", path: query, content: files[query] },
        ] } }] },
        { text: "", tool_calls: [{ id: "a7", name: "check_query", args: { source: "Origen e2e", path: query } }] },
        { text: "Integración lista.", tool_calls: [{ id: "a8", name: "finish_command", args: { summary: "Integración facturas-agente" } }] },
        // Run 2: the report spec; the run stops by itself when the project is ready.
        { text: "", tool_calls: [{ id: "b1", name: "edit_draft", args: { ops: [
          { op: "write", path: "reports/facturas-agente/report.yaml", content: files["reports/facturas-agente/report.yaml"] },
        ] } }] },
        { text: "", tool_calls: [{ id: "b2", name: "run_preview", args: {} }] },
      ],
    },
  });
  expect(scripted.ok()).toBe(true);

  await signIn(page);
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Facturas agente ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  for (const [path, content] of Object.entries(files)) {
    if (!path.startsWith("specs/")) continue;
    const r = await page.request.put(`/api/projects/${slug}/file`, { headers: FETCH, data: { path, content } });
    expect(r.ok(), path).toBe(true);
  }
  const session = await page.request.post("/api/assistant/sessions", { headers: FETCH, data: { project: slug } });
  const sid = ((await session.json()) as { id: number }).id;

  await setSpec(page, sid, INTEGRATION);
  let composer = await openChat(page, slug, sid);
  await composer.fill("/speckit-implement");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(`Ejecutó /speckit-implement en ${INTEGRATION}`)).toBeVisible({ timeout: 120_000 });
  await expect(page.locator('span[data-tool="check_query"]').first()).toContainText(
    `Comprobó la consulta ${query} en «Origen e2e» (correcta).`);
  await check(page);

  await setSpec(page, sid, REPORT);
  composer = await openChat(page, slug, sid);
  await composer.fill("/speckit-implement");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(`Ejecutó /speckit-implement en ${REPORT}`)).toBeVisible({ timeout: 120_000 });

  // The project is ready: preview PDF, then apply with step-up.
  await page.reload();
  await expect(page.getByText("Listo para aplicar").first()).toBeVisible({ timeout: 30_000 });
  await page.locator("summary", { hasText: "Vista previa" }).click();
  const previewPdf = page.waitForEvent("download");
  await page.getByRole("button", { name: "PDF de vista previa: facturas-agente" }).click();
  expect(await (await previewPdf).failure()).toBeNull();

  await page.getByRole("button", { name: "Aplicar proyecto" }).click();
  await page.getByRole("alert").getByRole("button", { name: "Confirmar" }).click();
  const stepUp = page.getByRole("region", { name: "Confirma tu contraseña" });
  await expect(stepUp).toBeVisible();
  await stepUp.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await stepUp.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.getByText(/Proyecto aplicado: versión \d+/)).toBeVisible({ timeout: 60_000 });
  await check(page);

  // The e2e has no worker process: run the active integration in-process (SC-003).
  const built = await hook<RunResult>(page, "/api/test/workspace/run", { integration: "facturas-agente" });
  expect(built.ok, built.message).toBe(true);
  expect(built.schema).toBe("app_test_e2e__ds_facturas_agente");
  expect(built.tables["facturas"]).toEqual(expect.arrayContaining([
    "numero", "fecha_emision", "emitida_en", "estado", "moneda", "monto_total", "impuesto",
  ]));
  expect(built.tables["facturas"]).not.toContain("cliente_email");
  expect(built.primary_keys["facturas"]).toEqual(["numero"]);
  expect(built.schedules.some((s) => s[0] === "facturas-agente" && s[2] === "0 * * * *")).toBe(true);

  // Dashboard visible for a normal user and its PDF export works (SC-003).
  const email = `agente-${info.project.name}-${Date.now()}@example.com`;
  const tempPassword = "Temporal-pass-55";
  const finalPassword = "Final-pass-5577";
  const createRes = await page.request.post("/api/admin/users", {
    headers: FETCH,
    data: { email, full_name: "Lector Agente", role: "user", temporary_password: tempPassword },
  });
  expect(createRes.status()).toBe(201);
  const user = (await createRes.json()) as { id: number };
  const grantRes = await page.request.put(`/api/admin/users/${user.id}/dashboards`, {
    headers: FETCH, data: { codes: ["facturas-agente"] },
  });
  expect(grantRes.status()).toBe(200);

  let userCtx: BrowserContext | undefined;
  try {
    userCtx = await browser.newContext();
    const userPage = await userCtx.newPage();
    await signIn(userPage, email, tempPassword);
    const pwRes = await userPage.request.post("/api/me/password", {
      headers: FETCH, data: { current_password: tempPassword, new_password: finalPassword },
    });
    expect(pwRes.status()).toBe(204);
    await userPage.goto("/tableros");
    const dashLink = userPage.getByRole("main").getByRole("link", { name: /Facturas del agente/ });
    await expect(dashLink).toBeVisible();
    await dashLink.click();
    await expect(userPage.getByRole("heading", { level: 1, name: "Facturas del agente" })).toBeVisible();
    await expect(userPage.getByRole("button", { name: "Abrir asistente" })).toHaveCount(0);
    await check(userPage);
    const reportPdf = userPage.waitForEvent("download");
    await userPage.getByRole("button", { name: "Descargar PDF" }).click();
    const reportDownload = await reportPdf;
    expect(reportDownload.suggestedFilename()).toMatch(/^facturas-agente.*\.pdf$/);
    expect(await reportDownload.failure()).toBeNull();
  } finally {
    await userCtx?.close();
  }
});
