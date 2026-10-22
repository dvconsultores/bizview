// Feature 020 T079 — BI projects end to end with the scripted fake provider (021 commands).
// SC-001 new project → `fuente` + direct `reporte` specs → apply → dashboard; SC-002 the disk
// equals the explorer after create, edit, agent change, restore and import; SC-003 every change
// in the history with actor and command; SC-004 axe at 375 px and a 30-file project under 1.5 s.
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
  [`specs/${REPORT_SPEC}/tasks.md`]: "- [ ] T001 Escribir reports/ventas-directo/report.yaml\n",
};
const REPORT_YAML = readFileSync(`${GOLDEN}/${REPORT_PATH}`, "utf8")
  .replace("spec: specs/001-ventas-directo", `spec: specs/${REPORT_SPEC}`);

async function signIn(page: Page) {
  await page.goto("/ingresar");
  await page.getByLabel("Correo electrónico").fill(SUPER.email);
  await page.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/ingresar/);
}

async function axe(page: Page) {
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" "))
    .join(" | ")} :: ${v.nodes.map((n) => (n.failureSummary ?? "").replace(/\n/g, " ")).join(" // ")}`))
    .toEqual([]);
}

/** The browser lays out the new geometry after the commit: reading a box in the same tick can still
 * return the previous one (measured: 208 px while the class was already the 5 rem rail). */
const settle = (page: Page) =>
  page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));

async function hook<T>(page: Page, path: string, data?: Record<string, unknown>): Promise<T> {
  const r = await page.request.post(path, { headers: FETCH, data });
  expect(r.ok(), `${path} should succeed`).toBe(true);
  return (await r.json()) as T;
}

/** SC-002: the files on disk are exactly the files the explorer lists. */
async function diskEqualsExplorer(page: Page, slug: string) {
  const disk = (await (await page.request.get(`/api/test/projects/${slug}/disk`)).json()) as { files: string[] };
  const tree = (await (await page.request.get(`/api/projects/${slug}/tree`)).json()) as {
    files: { path: string }[];
  };
  expect(tree.files.map((f) => f.path).sort()).toEqual(disk.files);
}

async function put(page: Page, slug: string, path: string, content: string) {
  const r = await page.request.put(`/api/projects/${slug}/file`, { headers: FETCH, data: { path, content } });
  expect(r.ok(), path).toBe(true);
}

async function confirmPassword(page: Page) {
  const stepUp = page.getByRole("region", { name: "Confirma tu contraseña" });
  await expect(stepUp).toBeVisible();
  await stepUp.getByLabel("Contraseña", { exact: true }).fill(SUPER.password);
  await stepUp.getByRole("button", { name: "Confirmar" }).click();
}

test.beforeEach(async ({ page }) => {
  await page.request.post("/api/test/assistant/reset", { headers: FETCH });
  const seeded = await hook<{ ok: boolean }>(page, "/api/test/direct/seed");
  expect(seeded.ok).toBe(true);
});

test.afterEach(async ({ page }) => {
  await page.request.post("/api/test/assistant/reset", { headers: FETCH });
  await hook(page, "/api/test/direct/reset");
});

test("new project → fuente + direct reporte → apply → dashboard; disk, history and import", async ({ page }, info) => {
  test.skip(info.project.name.endsWith("-320"), "flow checked once per engine");
  test.setTimeout(300_000);
  const scripted = await page.request.post("/api/test/assistant/script", {
    headers: FETCH,
    data: {
      steps: [
        { text: "", tool_calls: [{ id: "i1", name: "edit_draft", args: { ops: [
          { op: "write", path: REPORT_PATH, content: REPORT_YAML },
          { op: "replace", path: `specs/${REPORT_SPEC}/tasks.md`, old: "- [ ] T001", new: "- [X] T001" },
          { op: "replace", path: `specs/${REPORT_SPEC}/spec.md`, old: "**Status**: Approved", new: "**Status**: Implemented" },
        ] } }] },
        { text: "", tool_calls: [{ id: "i2", name: "check_query", args: { source: "bi", path: REPORT_PATH } }] },
        { text: "", tool_calls: [{ id: "i3", name: "run_preview", args: {} }] },
      ],
    },
  });
  expect(scripted.ok()).toBe(true);
  await signIn(page);

  // Create the project from the Proyectos page.
  const name = `Ventas directas ${Date.now()}`;
  await page.goto("/proyectos");
  await expect(page.getByRole("heading", { level: 1, name: "Proyectos" })).toBeVisible();
  await page.getByRole("button", { name: "Nuevo proyecto" }).click();
  const form = page.getByRole("form", { name: "Nuevo proyecto" });
  await form.getByLabel("Nombre").fill(name);
  await form.getByRole("button", { name: "Crear proyecto" }).click();
  await expect(page).toHaveURL(/\/proyectos\/[a-z0-9-]+\?chat=\d+/);
  const url = new URL(page.url());
  const slug = url.pathname.split("/")[2];
  const sid = Number(url.searchParams.get("chat"));
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await axe(page);
  await diskEqualsExplorer(page, slug);

  // The user writes the two specs (editor saves); the agent implements the report.
  for (const [path, content] of Object.entries(SPECS)) await put(page, slug, path, content);
  await diskEqualsExplorer(page, slug);
  const r = await page.request.patch(`/api/assistant/sessions/${sid}`, {
    headers: FETCH, data: { current_spec: REPORT_SPEC },
  });
  expect(r.ok()).toBe(true);
  await page.reload();
  const chatTab = page.getByRole("tab", { name: "Chat" });
  // Narrow layouts show tabs (Chat must be picked); wide ones show the composer at once.
  await expect(chatTab.or(page.getByLabel("Mensaje para el asistente")).first()).toBeVisible();
  if (await chatTab.isVisible()) await chatTab.click();
  await page.getByLabel("Mensaje para el asistente").fill("/speckit-implement");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(`Ejecutó /speckit-implement en ${REPORT_SPEC}`)).toBeVisible({ timeout: 120_000 });
  await diskEqualsExplorer(page, slug);

  // Apply (confirmation view + step-up), then the live dashboard.
  await page.reload();
  await expect(page.getByText("Listo para aplicar").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Aplicar proyecto" }).click();
  await page.getByRole("alert").getByRole("button", { name: "Confirmar" }).click();
  await confirmPassword(page);
  await expect(page.getByText(/Proyecto aplicado: versión \d+/)).toBeVisible({ timeout: 60_000 });
  await axe(page);
  await page.goto("/r/ventas-directo");
  await expect(page.getByRole("heading", { level: 1, name: "Ventas directo" })).toBeVisible();
  await expect(page.getByText(/Datos en vivo · BI de esta instalación · consultado/).first()).toBeVisible();

  // SC-003: history with actor and command for every change; restore makes a new revision.
  const history = (await (await page.request.get(`/api/projects/${slug}/history`)).json()) as {
    items: { actor?: string; command?: string; files?: { id: number; path: string }[]; event?: string }[];
  };
  const groups = history.items.filter((i) => i.files);
  expect(groups.every((g) => g.actor && g.command)).toBe(true);
  expect(groups.some((g) => g.actor === "user" && g.command === "edit")).toBe(true);
  expect(groups.some((g) => g.actor === "agent" && g.command === "/speckit-implement")).toBe(true);
  expect(history.items.some((i) => i.event === "project_applied")).toBe(true);
  const firstTasks = groups.flatMap((g) => g.files ?? [])
    .filter((f) => f.path === `specs/${REPORT_SPEC}/tasks.md`)
    .sort((a, b) => a.id - b.id)[0];
  const tree = (await (await page.request.get(`/api/projects/${slug}/tree`)).json()) as {
    files: { path: string; sha256: string }[];
  };
  const base = tree.files.find((f) => f.path === `specs/${REPORT_SPEC}/tasks.md`)?.sha256;
  const restored = await page.request.post(`/api/projects/${slug}/history/${firstTasks.id}/restore`, {
    headers: FETCH, data: { base_sha256: base },
  });
  expect(restored.ok(), await restored.text()).toBe(true);
  await diskEqualsExplorer(page, slug);
  const after = (await (await page.request.get(`/api/projects/${slug}/history`)).json()) as {
    items: { actor?: string; command?: string }[];
  };
  expect(after.items.some((i) => i.actor === "user" && i.command === "restore")).toBe(true);
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByText("Cambios sin aplicar").first()).toBeVisible();

  // Download the project and import it as a new one (step-up from the Proyectos page).
  const zip = await page.request.get(`/api/projects/${slug}/export.zip`);
  expect(zip.ok()).toBe(true);
  await page.goto("/proyectos");
  await page.locator("#project-zip").setInputFiles({
    name: `${slug}.zip`, mimeType: "application/zip", buffer: Buffer.from(await zip.body()),
  });
  // The apply above re-authenticated recently, so the step-up may not be asked again.
  const importedText = page.getByText(/Proyecto «.+» importado/);
  const stepUp = page.getByRole("region", { name: "Confirma tu contraseña" });
  await expect(stepUp.or(importedText).first()).toBeVisible({ timeout: 30_000 });
  if (await stepUp.isVisible()) await confirmPassword(page);
  await expect(importedText).toBeVisible({ timeout: 30_000 });
  const list = (await (await page.request.get("/api/projects")).json()) as {
    projects: { slug: string; name: string }[];
  };
  const imported = list.projects.find((p) => p.name === name && p.slug !== slug);
  expect(imported).toBeTruthy();
  await diskEqualsExplorer(page, imported!.slug);

  // Rollback in Espacio de trabajo removes the project's dashboard again.
  await page.goto("/admin/espacio");
  await page.getByRole("button", { name: "Volver a la versión anterior" }).click();
  const back = page.getByRole("region", { name: "¿Volver a la versión anterior?" });
  await back.getByRole("button", { name: "Volver a la anterior" }).click();
  await expect(back).toBeHidden({ timeout: 30_000 });
  await page.goto("/tableros");
  await expect(page.getByRole("main").getByRole("link", { name: /Ventas directo/ })).toHaveCount(0);
});

test("a 30-file project opens fast and passes axe at 375 px", async ({ page }, info) => {
  test.skip(info.project.name.endsWith("-320"), "checked once per engine");
  test.setTimeout(240_000);   // 28 setup writes, each revalidated against the remote database
  await signIn(page);
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Grande ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  for (let i = 0; i < 28; i += 1) {   // writes go through the file endpoint (/ops has none)
    const r = await page.request.put(`/api/projects/${slug}/file`, {
      headers: FETCH,
      data: { path: `integrations/carga/queries/q${String(i).padStart(2, "0")}.sql`,
              content: `SELECT ${i} AS n\n`, base_sha256: null },
    });
    expect(r.ok(), await r.text()).toBe(true);
  }
  await diskEqualsExplorer(page, slug);

  await page.setViewportSize({ width: 375, height: 740 });
  const started = Date.now();
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByRole("tree", { name: "Explorador de archivos" }).getByRole("treeitem").first())
    .toBeVisible();
  // SC-004's 1.5 s is on the reference machine (local database); here every request crosses
  // ~180 ms to the external test database, so the e2e bound allows for that.
  expect(Date.now() - started, "project opening time in ms").toBeLessThan(3000);
  await axe(page);
});

test("full screen project: the app chrome steps aside and comes back", async ({ page }, info) => {
  // The raised timeout comes first: `test.skip()` aborts the body, and the afterEach hook (which
  // resets the seeded schema over the remote database) keeps the config timeout otherwise.
  test.setTimeout(240_000);
  test.skip(info.project.name.endsWith("-320"), "desktop layout checked once per engine");
  await signIn(page);
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Pantalla ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  await page.goto(`/proyectos/${slug}`);

  // Like the TV mode of the report view, the control only exists where the Fullscreen API does
  // (iPhone Safari exposes none): the rest of the mode is checked where the button is rendered.
  const supported = await page.evaluate(
    () => "requestFullscreen" in document.documentElement
      || "webkitRequestFullscreen" in document.documentElement,
  );
  test.skip(!supported, "this engine has no Fullscreen API");

  // The header renders once the project is loaded (the tree proves it), with room to spare: every
  // request crosses ~180 ms to the external test database.
  await expect(page.getByRole("tree", { name: "Explorador de archivos" })).toBeVisible({ timeout: 30_000 });
  const nav = page.getByRole("navigation", { name: "Principal" });
  const enter = page.getByRole("button", { name: "Pantalla completa", exact: true });
  await expect(enter).toBeVisible({ timeout: 30_000 });
  await expect(nav).toBeVisible();

  await enter.click();
  await expect(page).toHaveURL(/full=1/);
  await expect(nav).toBeHidden();
  await expect(page.getByRole("button", { name: "Salir de pantalla completa", exact: true })).toBeVisible();
  // The page keeps working with the chrome out of the way.
  await expect(page.getByRole("tree", { name: "Explorador de archivos" })).toBeVisible();

  await page.getByRole("button", { name: "Salir de pantalla completa", exact: true }).click();
  await expect(page).not.toHaveURL(/full=1/);
  await expect(nav).toBeVisible();
  await page.evaluate(() => document.exitFullscreen?.().catch(() => undefined));
});

test("full screen keeps the chat: the panel is there and the project's own controls stay reachable", async ({ page }, info) => {
  test.setTimeout(240_000);
  test.skip(info.project.name.endsWith("-320"), "desktop layout checked once per engine");
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await page.request.post("/api/test/assistant/script", { headers: FETCH, data: { steps: [{ text: "Hola" }] } });
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Chat completo ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByRole("tree", { name: "Explorador de archivos" })).toBeVisible({ timeout: 30_000 });

  const supported = await page.evaluate(
    () => "requestFullscreen" in document.documentElement
      || "webkitRequestFullscreen" in document.documentElement,
  );
  test.skip(!supported, "this engine has no Fullscreen API");

  await page.getByRole("button", { name: "Pantalla completa", exact: true }).click();
  await expect(page).toHaveURL(/full=1/);

  // The chat is opened from the project's own tool strip (the top bar is gone in full screen).
  const toggle = page.getByRole("button", { name: "Asistente", exact: true });
  await toggle.click();
  const panel = page.locator("#assistant-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel("Mensaje para el asistente")).toBeVisible();

  // It starts at the very top: no 4 rem gap where the top bar used to be.
  await settle(page);
  const top = await panel.evaluate((el) => el.getBoundingClientRect().top);
  expect(top, "the panel owns the whole height in full screen").toBeLessThanOrEqual(1);

  // The chrome is aside but the page keeps its room: the tool strip is not under the panel.
  const strip = await page.getByRole("button", { name: "Pantalla completa", exact: true })
    .or(page.getByRole("button", { name: "Salir de pantalla completa", exact: true })).first().boundingBox();
  const panelBox = await panel.boundingBox();
  expect(strip!.x + strip!.width, "the tool strip ends before the panel").toBeLessThanOrEqual(panelBox!.x + 1);

  // And the conversation works from there.
  await panel.getByLabel("Mensaje para el asistente").fill("¿Qué hay en este proyecto?");
  await panel.getByLabel("Mensaje para el asistente").press("Enter");
  await expect(panel.getByText("¿Qué hay en este proyecto?")).toBeVisible({ timeout: 30_000 });

  // Leaving full screen keeps the chat open (the person's choice is not forgotten).
  await page.getByRole("button", { name: "Salir de pantalla completa", exact: true }).click();
  await expect(panel).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Principal" })).toBeVisible();
  await page.evaluate(() => document.exitFullscreen?.().catch(() => undefined));
  await axe(page);
});

test("one chat on a wide screen: the docked panel, not a second copy", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  // The chat is only offered when AI is configured (the harness scripts the fake provider).
  await page.request.post("/api/test/assistant/script", { headers: FETCH, data: { steps: [{ text: "Hola" }] } });
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Un chat ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByRole("tree", { name: "Explorador de archivos" })).toBeVisible({ timeout: 30_000 });

  // The page itself offers no chat: no Chat tab and no second composer (feature 024 polish).
  await expect(page.getByRole("tab", { name: "Chat" })).toHaveCount(0);
  await expect(page.getByLabel("Mensaje para el asistente")).toHaveCount(0);

  // The chat is the same one as everywhere: opened from the project header, it is the panel.
  const toggle = page.getByRole("button", { name: "Asistente", exact: true });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await toggle.click();
  const panel = page.locator("#assistant-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel("Mensaje para el asistente")).toBeVisible();
  await expect(page.getByLabel("Mensaje para el asistente")).toHaveCount(1);   // exactly one
  await expect(toggle).toHaveAttribute("aria-pressed", "true");

  // The panel owns the whole height of its column (feature 025): it used to start below the top
  // bar, which left a band of empty canvas above it.
  await settle(page);
  const box = (await panel.boundingBox())!;
  expect(box.y, "the panel starts at the top of the viewport").toBeLessThanOrEqual(1);
  expect(box.height, "the panel reaches the bottom").toBeGreaterThanOrEqual(899);
  const empty = await page.evaluate(() => {
    const el = document.elementFromPoint(window.innerWidth - 8, 4);
    return el?.closest("#assistant-panel") !== null;
  });
  expect(empty, "nothing but the panel in its top corner").toBe(true);
  // …and it covers its own column only: the header's own controls stay clickable.
  const toggleBox = (await toggle.boundingBox())!;
  expect(toggleBox.x + toggleBox.width, "the top bar ends before the panel").toBeLessThanOrEqual(box.x + 1);
  // No blank seam between the page and the chat (feature 025): the content column's right padding
  // is zero while the panel is docked, and the panel's own edge is the IDE's divider, not a shadow
  // that spills into the page.
  const mainBox = (await page.locator("#main").boundingBox())!;
  expect(box.x - (mainBox.x + mainBox.width), "the gap between the page and the chat").toBeLessThanOrEqual(1);
  const seam = await panel.evaluate((el) => {
    // The panel's edge is its resize handle now (owner, 2026-10-21: resizable like VS Code); it
    // keeps the IDE divider's look: same strip, same colour, no shadow.
    const strip = el.querySelector("[data-assistant-resizer]")!;
    const divider = document.querySelector('#main [role="separator"]')
      ?? document.querySelector('[role="separator"]')!;
    return {
      strip: getComputedStyle(strip).width,
      divider: getComputedStyle(divider).width,
      shadow: getComputedStyle(el).boxShadow,
      stripColour: getComputedStyle(strip).backgroundColor,
      dividerColour: getComputedStyle(divider).backgroundColor,
    };
  });
  expect(seam.strip, "the panel's edge is the IDE's divider").toBe(seam.divider);
  expect(seam.stripColour, "same colour as the divider").toBe(seam.dividerColour);
  expect(seam.shadow, "no halo spilling into the page").toBe("none");

  // On a wide screen the content used to be capped and centered, leaving canvas in front of the
  // chat; with the panel docked it takes the whole column.
  await page.setViewportSize({ width: 2560, height: 1200 });
  await page.waitForFunction(() => window.innerWidth === 2560);
  await settle(page);
  const wide = await page.evaluate(() => {
    const m = document.querySelector("#main")!.getBoundingClientRect();
    const p = document.querySelector("#assistant-panel")!.getBoundingClientRect();
    return { gap: Math.round(p.x - m.right), canvas: Math.round(document.documentElement.scrollWidth - window.innerWidth) };
  });
  expect(wide.gap, "no gap on a wide screen either").toBeLessThanOrEqual(1);
  expect(wide.canvas, "no horizontal overflow").toBeLessThanOrEqual(0);
  await page.setViewportSize({ width: 1440, height: 900 });

  await toggle.click();
  await expect(panel).toBeHidden();
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
    .toBeLessThanOrEqual(0);
});

test("phones keep the chat as a pane (the panel cannot dock)", async ({ page }, info) => {
  test.setTimeout(240_000);
  test.skip(!info.project.name.endsWith("-375"), "checked once per engine");
  await signIn(page);
  await page.request.post("/api/test/assistant/script", { headers: FETCH, data: { steps: [{ text: "Hola" }] } });
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Movil ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  await page.goto(`/proyectos/${slug}`);
  const tab = page.getByRole("tab", { name: "Chat" });
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click();
  await expect(page.getByLabel("Mensaje para el asistente")).toBeVisible();
});

test("the docked chat resizes like an editor's pane", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await page.request.post("/api/test/assistant/script", { headers: FETCH, data: { steps: [{ text: "Hola" }] } });
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Redimension ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByRole("tree", { name: "Explorador de archivos" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Asistente", exact: true }).click();
  const panel = page.locator("#assistant-panel");
  await expect(panel).toBeVisible();
  await settle(page);

  const start = (await panel.boundingBox())!.width;
  const seam = page.locator("[data-assistant-resizer]");
  await expect(seam).toHaveAttribute("role", "separator");
  await expect(seam).toHaveAttribute("aria-orientation", "vertical");

  // Drag the seam 140 px to the left: the chat grows and the page keeps its room.
  const box = (await seam.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 240);
  await page.mouse.down();
  await page.mouse.move(box.x - 140, box.y + 240, { steps: 10 });
  await page.mouse.up();
  await settle(page);
  const wider = (await panel.boundingBox())!.width;
  expect(wider, "the panel follows the drag").toBeGreaterThan(start + 100);
  const overlap = await page.evaluate(() => {
    const main = document.querySelector("#main")!.getBoundingClientRect();
    const chat = document.querySelector("#assistant-panel")!.getBoundingClientRect();
    return Math.round(chat.x - main.right);
  });
  expect(overlap, "the page is not under the chat").toBeLessThanOrEqual(1);

  // The choice is remembered for the next visit.
  const stored = await page.evaluate(() => localStorage.getItem("bizview.assistantPanel.width"));
  expect(Number(stored)).toBeGreaterThan(start + 100);
  await page.reload();
  await expect(page.locator("#assistant-panel")).toBeVisible();
  await settle(page);
  expect((await page.locator("#assistant-panel").boundingBox())!.width)
    .toBeGreaterThan(start + 100);

  // The keyboard works the same seam, and the panel never eats the whole screen.
  await seam.focus();
  await page.keyboard.press("End");
  await settle(page);
  const widest = (await panel.boundingBox())!.width;
  expect(widest, "70 % of 1440 px at most").toBeLessThanOrEqual(Math.round(1440 * 0.7) + 1);
  const canvas = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(canvas, "no horizontal overflow at the widest panel").toBeLessThanOrEqual(0);
  await page.keyboard.press("Home");
  await settle(page);
  expect((await panel.boundingBox())!.width).toBeLessThan(widest);
  await page.keyboard.press("Enter");
  await settle(page);
  await axe(page);
});

test("the project toolbar is compact and the type scale follows the reference app", async ({ page }, info) => {
  test.setTimeout(240_000);
  test.skip(!info.project.name.endsWith("-375"), "checked once per engine");
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  const created = await page.request.post("/api/projects", { headers: FETCH, data: { name: `Tipografia ${Date.now()}` } });
  expect(created.status()).toBe(201);
  const slug = ((await created.json()) as { slug: string }).slug;
  await page.goto(`/proyectos/${slug}`);
  await expect(page.getByRole("tree", { name: "Explorador de archivos" })).toBeVisible({ timeout: 30_000 });

  // The base size follows the reference app (Customer A's stylesheet: 13 px, 13.5 px from 1536 px).
  // Phones keep 15 px so the 16 px form controls stay proportional.
  for (const [width, expected] of [[1440, 13], [1024, 13], [768, 13], [1920, 13.5]] as const) {
    await page.setViewportSize({ width, height: 900 });
    // The resize lands asynchronously, and the media query's style recalc with it: without these
    // two waits the computed style is still the previous viewport's.
    await page.waitForFunction((w) => window.innerWidth === w, width);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const base = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
    expect(base, `root font size at ${width} px`).toBe(expected);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));

  // Nothing in the shell is hardcoded above the scale: the sidebar's brand and its navigation use
  // rem sizes, so they render at the root (13 px here) — the size the reference app's sidebar shows.
  const sidebarFonts = await page.evaluate(() => {
    const nav = document.querySelector('nav[aria-label="Principal"]')!;
    return {
      brand: parseFloat(getComputedStyle(nav.parentElement!.querySelector("p")!).fontSize),
      link: parseFloat(getComputedStyle(nav.querySelector("a")!).fontSize),
    };
  });
  expect(sidebarFonts.brand, "sidebar brand follows the scale").toBe(13);
  expect(sidebarFonts.link, "sidebar navigation follows the scale").toBe(13);

  // The back control is the shared one: an arrow and "Volver", never the destination's name.
  const back = page.getByRole("link", { name: "Volver", exact: true });
  await expect(back).toBeVisible();
  await expect(page.getByText("Volver a proyectos")).toHaveCount(0);

  // The tool strip holds its controls at 36 px with a mouse and never larger than the touch
  // target, and it stays on one line with the title (nothing wraps under the header).
  for (const name of ["Vista previa", "Descargar", "Historial"]) {
    const control = page.getByRole("button", { name, exact: true })
      .or(page.getByRole("link", { name, exact: true })).first();
    await expect(control).toBeVisible();
    const box = await control.boundingBox();
    expect(box!.height, `${name} height`).toBeLessThanOrEqual(44);
    expect(box!.height, `${name} height`).toBeGreaterThanOrEqual(30);
  }
  const header = page.locator("header").filter({ has: page.getByRole("button", { name: "Aplicar proyecto" }) });
  const headerBox = await header.boundingBox();
  // One row: two rows of controls would be at least 2 × 44 px (the touch target under a finger).
  expect(headerBox!.height, "header rows").toBeLessThan(80);
  const apply = await page.getByRole("button", { name: "Aplicar proyecto" }).boundingBox();
  expect(Math.abs(apply!.y - headerBox!.y), "the actions share the title's line").toBeLessThan(24);
  await axe(page);
});

test("the projects list is searchable by name, identifier and description", async ({ page }, info) => {
  test.setTimeout(240_000);
  test.skip(info.project.name.endsWith("-320"), "desktop layout checked once per engine");
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  const stamp = Date.now();
  const alpha = `E2E ${stamp} Alfa`;
  const beta = `E2E ${stamp} Beta`;
  for (const [name, description] of [[alpha, "Compras y pagos"], [beta, "Nómina mensual"]] as const) {
    const created = await page.request.post("/api/projects", { headers: FETCH, data: { name, description } });
    expect(created.status()).toBe(201);
  }
  await page.goto("/proyectos");
  const search = page.getByLabel("Buscar proyectos");
  await expect(search).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: new RegExp(alpha) })).toBeVisible();

  // Filtering is local: typing does not ask the server for anything.
  let asked = 0;
  page.on("request", (r) => { if (r.url().includes("/api/projects")) asked += 1; });

  await search.fill(`E2E ${stamp} Alfa`);
  await expect(page.getByRole("link", { name: new RegExp(alpha) })).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(beta) })).toHaveCount(0);
  await expect(page.getByText("1 coincidencia")).toBeVisible();

  // Accents and case are ignored, at either end of the term.
  await search.fill("NOMINA");
  await expect(page.getByRole("link", { name: new RegExp(beta) })).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(alpha) })).toHaveCount(0);

  await search.fill(`sin-resultados-${stamp}`);
  await expect(page.getByText(`Ningún proyecto coincide con «sin-resultados-${stamp}».`)).toBeVisible();
  await expect(page.getByText("Crea un proyecto o pide al asistente")).toHaveCount(0);

  await page.getByRole("button", { name: "Limpiar la búsqueda" }).last().click();
  await expect(search).toHaveValue("");
  await expect(page.getByRole("link", { name: new RegExp(alpha) })).toBeVisible();
  expect(asked, "filtering never reaches the API").toBe(0);

  await search.fill(`E2E ${stamp} Beta`);
  await axe(page);
});

test("the left menu collapses to an icon rail and the page follows it", async ({ page }, info) => {
  test.setTimeout(240_000);
  test.skip(info.project.name.endsWith("-320"), "desktop layout checked once per engine");
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);

  const nav = page.getByRole("navigation", { name: "Principal" }).first();
  const link = nav.getByRole("link", { name: "Proyectos" });
  await expect(link).toBeVisible();
  await settle(page);
  const expanded = (await nav.boundingBox())!;

  const collapse = page.getByRole("button", { name: "Contraer el menú" });
  await expect(collapse).toHaveAttribute("aria-expanded", "true");
  await collapse.click();

  // A rail: a fraction of the menu's width, with the label kept for assistive technology (sr-only)
  // and a tooltip for the mouse, and the content starting where the rail ends.
  await expect(page.getByRole("button", { name: "Expandir el menú" })).toBeVisible();
  await settle(page);
  const rail = (await nav.boundingBox())!;
  expect(rail.width, "the rail is much narrower").toBeLessThan(expanded.width / 2);
  await expect(link).toHaveAttribute("title", "Proyectos");
  const linkBox = (await link.boundingBox())!;
  expect(linkBox.height, "the target keeps its size").toBeGreaterThanOrEqual(24);
  const main = (await page.locator("#main").boundingBox())!;
  expect(main.x, "the content follows the rail").toBeLessThanOrEqual(rail.x + rail.width + 2);

  // The choice is remembered by the device.
  await page.reload();
  await expect(page.getByRole("button", { name: "Expandir el menú" })).toBeVisible();
  await settle(page);
  expect((await nav.boundingBox())!.width, "still a rail after the reload").toBeLessThan(expanded.width / 2);
  await page.getByRole("button", { name: "Expandir el menú" }).click();
  await expect(page.getByRole("button", { name: "Contraer el menú" })).toBeVisible();
  await settle(page);
  expect((await nav.boundingBox())!.width, "expanded again").toBeGreaterThan(expanded.width / 2);
  await expect(link).toBeVisible();
  await axe(page);
});
