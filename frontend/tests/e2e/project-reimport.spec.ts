// Feature 055 — re-importing a project is a new revision of it, not a second project.
// The journey of the brief: import v1 → apply → import v2 (changed report.yaml) → the diff is shown
// → apply → the dashboard shows the new layout → revert → the old layout is back.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const GOLDEN = resolve(process.cwd(), "../cli/bizview_cli/golden-direct/projects/ejemplo");
const REPORT_PATH = "reports/ventas-directo/report.yaml";
const SOURCE_SPEC = "001-bi";
const REPORT_SPEC = "002-ventas-directo";

const SPECS: Record<string, string> = {
  [`specs/${SOURCE_SPEC}/spec.md`]:
    "# BI de esta instalación\n\n**Tipo**: fuente\n**Status**: Implemented\n\n**Fuente**: bi\n",
  [`specs/${SOURCE_SPEC}/plan.md`]: "# Plan\n\nLa base BI ya existe; no hay artefactos.\n",
  [`specs/${SOURCE_SPEC}/tasks.md`]: "- [X] T001 Comprobar la base BI\n",
  [`specs/${REPORT_SPEC}/spec.md`]: readFileSync(`${GOLDEN}/specs/001-ventas-directo/spec.md`, "utf8"),
  [`specs/${REPORT_SPEC}/plan.md`]: readFileSync(`${GOLDEN}/specs/001-ventas-directo/plan.md`, "utf8"),
  // Ticked from the start: readiness treats an open task as a warning, and `valid` is what lets
  // the origin check (and therefore the apply) run.
  [`specs/${REPORT_SPEC}/tasks.md`]: "- [X] T001 Escribir reports/ventas-directo/report.yaml\n",
};
const REPORT_YAML = readFileSync(`${GOLDEN}/${REPORT_PATH}`, "utf8")
  .replace("spec: specs/001-ventas-directo", `spec: specs/${REPORT_SPEC}`);

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
  await reauth(page);
}

async function expectAccessible(page: Page, where: string) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, `${where}: horizontal overflow`).toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${where} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`))
    .toEqual([]);
}

const stepUpRegion = (page: Page) => page.getByRole("region", { name: "Confirma tu contraseña" });

async function answerStepUp(page: Page) {
  const stepUp = stepUpRegion(page);
  await expect(stepUp).toBeVisible({ timeout: 20_000 });
  await stepUp.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await stepUp.getByRole("button", { name: "Confirmar" }).click();
  await expect(stepUp).toBeHidden({ timeout: 20_000 });
}

/** The step-up window, opened once through the API: every later sensitive call is covered. */
async function reauth(page: Page) {
  const r = await page.request.post("/api/auth/reauth", {
    headers: FETCH, data: { password: SUPER.password },
  });
  expect(r.status()).toBe(204);
}

/**
 * The apply itself (its confirmation and its step-up) is feature 020's e2e; here it is the call that
 * turns a draft revision into the applied one, so the journey can move on.
 */
async function applyViaApi(page: Page, slug: string, revision: number) {
  const r = await page.request.post(`/api/projects/${slug}/apply`, { headers: FETCH });
  expect(r.ok(), await r.text()).toBe(true);
  const chip = r.ok() ? ((await r.json()) as { project: { revision: { number: number;
    status: string } } }).project.revision : null;
  expect(chip).toMatchObject({ number: revision, status: "applied" });
}

async function zipOf(page: Page, name: string, files: Record<string, string>): Promise<Buffer> {
  const manifest = `name: "${name}"\nslug: ""\n`;
  const zip = await page.request.post("/api/test/zip", {
    headers: FETCH, data: { entries: { "project.yaml": manifest, ...files } },
  });
  expect(zip.ok(), await zip.text()).toBe(true);
  return Buffer.from(await zip.body());
}

/** Choose the archive and press **Importar ahora** twice: the first press is the dry run (055). */
async function importArchive(page: Page, fileName: string, buffer: Buffer) {
  await page.goto("/proyectos");
  await page.locator("#project-zip").setInputFiles({
    name: fileName, mimeType: "application/zip", buffer,
  });
  const now = page.getByRole("button", { name: "Importar ahora" });
  const diff = page.getByTestId("revision-diff");
  await expect(now).toBeVisible({ timeout: 30_000 });

  // First press: the server answers the diff. The import asks for the password once (step-up).
  await now.click();
  await expect(stepUpRegion(page).or(diff).first()).toBeVisible({ timeout: 30_000 });
  if (await stepUpRegion(page).isVisible()) await answerStepUp(page);
  await expect(diff).toBeVisible({ timeout: 30_000 });

  // Second press: it is written. The window is open now, so no password should be asked again.
  await now.click();
  await expect(page.getByText(/Proyecto «.+»/)).toBeVisible({ timeout: 60_000 });
}

/** The title the dashboard currently serves: what "applied" means for the reader. */
async function servedTitle(page: Page): Promise<string> {
  const r = await page.request.get("/api/reports/ventas-directo");
  expect(r.ok(), await r.text()).toBe(true);
  return ((await r.json()) as { title: string }).title;
}

/** The origin check the readiness asks for (`Volver a comprobar`), then reload. */
async function recheck(page: Page, slug: string) {
  const r = await page.request.post(`/api/projects/${slug}/validate?check_origin=true`,
                                    { headers: FETCH });
  expect(r.ok(), await r.text()).toBe(true);
  await page.reload();
}

test.beforeEach(async ({ page }) => {
  const seeded = await page.request.post("/api/test/direct/seed", { headers: FETCH });
  expect(seeded.ok(), await seeded.text()).toBe(true);
});

test.afterEach(async ({ page }) => {
  await page.request.post("/api/test/direct/reset", { headers: FETCH });
});

async function projects(page: Page) {
  return (await (await page.request.get("/api/projects")).json()) as {
    projects: { id: number; slug: string; name: string }[];
  };
}

test("import v1, apply, re-import v2, apply, revert (055)", async ({ page }, info) => {
  test.skip(info.project.name.endsWith("-320"), "flow checked once per engine");
  test.setTimeout(300_000);
  const name = `Reimpresión ${info.project.name} ${Date.now()}`;
  await signIn(page);

  // --- v1: a project from an archive -----------------------------------------------------------
  await importArchive(page, "v1.zip", await zipOf(page, name, { ...SPECS,
    [REPORT_PATH]: REPORT_YAML }));
  const created = (await projects(page)).projects.filter((p) => p.name === name);
  expect(created).toHaveLength(1);
  const slug = created[0].slug;
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByText("rev 1 · borrador")).toBeVisible({ timeout: 20_000 });
  await recheck(page, slug);
  await applyViaApi(page, slug, 1);
  await page.reload();
  await expect(page.getByText("rev 1 · aplicada")).toBeVisible({ timeout: 30_000 });
  const titleV1 = await servedTitle(page);

  // --- v2: the same slug, one changed report ----------------------------------------------------
  const v2 = REPORT_YAML.replace(/^title:.*$/m, `title: ${JSON.stringify(`${name} v2`)}`);
  await importArchive(page, "v2.zip", await zipOf(page, name, { ...SPECS, [REPORT_PATH]: v2 }));
  // The diff the page showed before writing: only the report changed, against revision 1 — the
  // manifest is rewritten with the project's own slug, so it is not a change at all.
  const diff = page.getByTestId("revision-diff");
  await expect(diff).toContainText("Comparado con la revisión 1: 1 cambiado.", { timeout: 30_000 });
  await expect(diff).toContainText("Modificado");
  await page.getByText("Ver los archivos afectados").last().click();
  await expect(diff).toContainText(REPORT_PATH);
  // Still one project: the archive was a revision, not a duplicate.
  const after = (await projects(page)).projects.filter((p) => p.name === name);
  expect(after).toHaveLength(1);
  expect(after[0].id).toBe(created[0].id);

  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByText("rev 2 · borrador")).toBeVisible({ timeout: 20_000 });
  // Nothing was applied: the dashboard still serves revision 1.
  expect(await servedTitle(page)).toBe(titleV1);
  await recheck(page, slug);

  await applyViaApi(page, slug, 2);
  expect(await servedTitle(page)).toBe(`${name} v2`);
  await page.reload();
  await expect(page.getByText("rev 2 · aplicada")).toBeVisible({ timeout: 30_000 });

  // --- the revisions panel: download and go back ------------------------------------------------
  await page.getByText("Revisiones").first().click();
  await expect(page.getByRole("button", { name: "Volver a esta revisión" }).first())
    .toBeVisible({ timeout: 20_000 });
  await expectAccessible(page, "revisiones");
  // Back to the first revision, the one the reader had before this import.
  const rev1 = page.locator("li").filter({ has: page.getByText("Rev 1", { exact: true }) });
  await rev1.getByRole("button", { name: "Volver a esta revisión" }).click();
  await rev1.getByRole("button", { name: "Confirmar" }).click();
  const restored = page.getByText(/Revisión 1 restaurada/);
  await expect(stepUpRegion(page).or(restored).first()).toBeVisible({ timeout: 60_000 });
  if (await stepUpRegion(page).isVisible()) await answerStepUp(page);
  await expect(restored).toBeVisible({ timeout: 60_000 });
  // The older layout serves the dashboard again.
  expect(await servedTitle(page)).toBe(titleV1);
  const audit = (await (await page.request.get("/api/admin/audit?kind=project_reverted")).json()) as {
    items: unknown[];
  };
  expect(audit.items.length).toBeGreaterThan(0);
});
