// Feature 065, verification B: the point of the feature, proved in a real browser through the real
// edge. Two host pages are served from two origins (localhost ports are distinct origins); one is on
// the widget's allowed list and one is not. The widget document is served by Caddy with this
// repository's own Caddyfile — so the framing decision is the backend's per-widget answer, copied by
// `forward_auth`, and every other route keeps the site-wide refusal.
//
// The spec needs:
//   * a Caddy binary: `CADDY_BIN=/path/to/caddy` or `caddy` on PATH;
//   * a built frontend (`frontend/dist`, produced by the e2e webServer's `npm run build`).
// Without them the cross-origin case is skipped, and the rest of the suite still runs.
import { expect, test, type BrowserContext } from "@playwright/test";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { createServer, type Server } from "node:http";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SUPER = { email: "e2e-root@example.com", password: "E2e-super-pass-1" };
const FETCH = { "X-Requested-With": "fetch" };
const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const ROOT = resolve(FRONTEND, "..");
const DIST = join(FRONTEND, "dist");
const CADDY = (process.env.CADDY_BIN
  ?? spawnSync("sh", ["-c", "command -v caddy"], { encoding: "utf8" }).stdout).trim();

const available = Boolean(CADDY) && existsSync(DIST);
test.skip(!available, "needs a caddy binary (CADDY_BIN) and a built frontend (dist)");

async function freePort(): Promise<number> {
  return await new Promise((done, fail) => {
    const probe = createServer();
    probe.on("error", fail);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address() as { port: number };
      probe.close(() => done(port));
    });
  });
}

/** A host page on its own origin; `setPage` swaps what it serves once the snippet exists. */
async function hostPage(): Promise<{ origin: string; setPage: (html: string) => void; close: () => Promise<void> }> {
  let html = "<!doctype html><title>host</title><p>host</p>";
  const server: Server = createServer((_request, response) => {
    response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" });
    response.end(html);
  });
  await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  const { port } = server.address() as { port: number };
  return {
    origin: `http://127.0.0.1:${port}`,
    setPage: (next) => {
      html = next;
    },
    close: () => new Promise<void>((done) => server.close(() => done())),
  };
}

let caddy: ChildProcess | null = null;
let edge = "";

test.beforeAll(async () => {
  if (!available) return;
  const work = mkdtempSync(join(tmpdir(), "bizview-widget-edge-"));
  writeFileSync(join(work, "tls.snippet"), "");
  // The real Caddyfile, with only the three addresses the test controls replaced: the certificate
  // snippet, the backend (the e2e API on 8001) and the static root (the built SPA).
  const config = readFileSync(join(ROOT, "deploy", "caddy", "Caddyfile"), "utf8")
    .replace("import /etc/caddy/tls.snippet", `import ${join(work, "tls.snippet")}`)
    .replace(/backend:8000/g, "127.0.0.1:8001")
    .replace(/root \* \/srv/g, `root * ${DIST}`);
  writeFileSync(join(work, "Caddyfile"), config);
  const port = await freePort();
  edge = `http://127.0.0.1:${port}`;
  caddy = spawn(CADDY, ["run", "--config", join(work, "Caddyfile"), "--adapter", "caddyfile"], {
    env: { ...process.env, SITE_ADDRESS: `:${port}` },
    stdio: "ignore",
  });
  // The SPA document answers on any path (try_files → index.html); that is the readiness signal.
  await expect
    .poll(async () => (await fetch(`${edge}/ingresar`).then((r) => r.status).catch(() => 0)),
          { timeout: 60_000 })
    .toBe(200);
});

test.afterAll(async () => {
  caddy?.kill("SIGTERM");
  caddy = null;
});

test("a listed site frames the widget and the widget resizes; an unlisted one gets nothing", async ({
  browser,
  request,
}, testInfo) => {
  test.slow();
  const listedHost = await hostPage();
  const unlistedHost = await hostPage();
  try {
    // A real session through the edge, then the installation switch and a widget whose only allowed
    // site is the first host page's origin.
    const login = await request.post(`${edge}/api/auth/login`, { headers: FETCH, data: SUPER });
    expect(login.ok()).toBeTruthy();
    const settings = await request.post(`${edge}/api/test/settings`, {
      headers: FETCH,
      data: { share_links_enabled: true, embed_widgets_enabled: true, widget_rate_limit: 300 },
    });
    expect(settings.ok()).toBeTruthy();
    const created = await request.post(`${edge}/api/dashboards/ventas/widgets`, {
      headers: FETCH,
      data: { name: "Sitio del cliente", sites: [listedHost.origin] },
    });
    expect(created.ok()).toBeTruthy();
    const widget = (await created.json()) as { id: number; key: string; snippet: string; url: string };
    const document = `${edge}/w/${widget.key}`;
    // The snippet carries the installation's public address (`SITE_ADDRESS`), which in a real
    // deployment is this edge. This test environment serves the edge on a random local port, so the
    // address in the pasted snippet is pointed at it — the only thing a developer would change.
    const publicOrigin = new URL(widget.url).origin;
    const snippet = widget.snippet.split(publicOrigin).join(edge);

    // Both host pages are exactly what a developer pastes: the snippet, nothing else.
    const pageHtml = (title: string, html: string) => `<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>${title}</title></head><body>${html}</body></html>`;
    listedHost.setPage(pageHtml("Página del cliente", snippet));
    unlistedHost.setPage(pageHtml("Otro sitio", snippet));

    const contextOptions = {
      viewport: testInfo.project.use.viewport ?? { width: 1280, height: 800 },
      locale: testInfo.project.use.locale as string,
    };
    const listed = await browser.newContext(contextOptions);
    const unlisted = await browser.newContext(contextOptions);
    try {
      const visits = async (): Promise<number> => {
        const listing = await request.get(`${edge}/api/dashboards/ventas/widgets`);
        const items = ((await listing.json()) as { items: { id: number; visits: number }[] }).items;
        return items.find((item) => item.id === widget.id)?.visits ?? -1;
      };

      // 1. The listed origin: the dashboard renders inside the host page, without the product's
      //    chrome, and its height travels to the host (the widget grows to its content).
      const listedPage = await listed.newPage();
      const apiCalls: string[] = [];
      listedPage.on("request", (r) => {
        if (r.url().startsWith(`${edge}/api/widgets/`)) apiCalls.push(r.url());
      });
      await listedPage.goto(listedHost.origin);
      const frame = listedPage.frameLocator("iframe");
      await expect(frame.getByRole("heading", { level: 1, name: "Ventas", exact: true }))
        .toBeVisible({ timeout: 30_000 });
      await expect(frame.getByRole("region", { name: "Indicadores" })).toBeVisible();
      await expect(frame.getByRole("navigation")).toHaveCount(0);
      expect(apiCalls.some((url) => url.startsWith(`${edge}/api/widgets/`))).toBe(true);
      // The snippet starts the iframe at its min-height; the widget's message sets a real one.
      await expect
        .poll(async () => listedPage.evaluate(() =>
          (document.querySelector("iframe") as HTMLElement | null)?.style.height ?? ""))
        .toMatch(/^\d+px$/);
      const height = await listedPage.evaluate(() =>
        parseInt((document.querySelector("iframe") as HTMLElement).style.height, 10));
      expect(height).toBeGreaterThan(320);
      expect(await visits()).toBeGreaterThan(0);

      // 2. The unlisted origin: the edge refuses the frame, so the widget's document never runs —
      //    no call to its API and its visit counter does not move — and the snippet's script never
      //    sets a height.
      const before = await visits();
      const unlistedPage = await unlisted.newPage();
      const unlistedApiCalls: string[] = [];
      unlistedPage.on("request", (r) => {
        if (r.url().startsWith(`${edge}/api/widgets/`)) unlistedApiCalls.push(r.url());
      });
      await unlistedPage.goto(unlistedHost.origin);
      await unlistedPage.waitForTimeout(3000);
      expect(unlistedApiCalls, "the widget's API must not run inside an unlisted site").toEqual([]);
      expect(await visits(), "the widget's document must not run inside an unlisted site")
        .toBe(before);
      expect(await unlistedPage.evaluate(() =>
        (document.querySelector("iframe") as HTMLElement | null)?.style.height ?? "")).toBe("");
      const bodies = await Promise.all(unlistedPage.frames().map(async (f) => {
        try {
          return await f.locator("body").innerText({ timeout: 1000 });
        } catch {
          return "";
        }
      }));
      expect(bodies.join(" ")).not.toContain("Indicadores");
      expect(bodies.join(" ")).not.toContain("Ventas netas");
    } finally {
      await listed.close();
      await unlisted.close();
    }
  } finally {
    await listedHost.close();
    await unlistedHost.close();
    await request.post(`${edge}/api/test/settings/reset`, { headers: FETCH });
  }
});
