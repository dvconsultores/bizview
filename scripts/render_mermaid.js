#!/usr/bin/env node
/**
 * Render a Mermaid source to a standalone SVG (feature 057b).
 *
 *   node scripts/render_mermaid.js docs/assets/rendering.mmd docs/assets/rendering.svg
 *
 * Playwright ships with the frontend (`frontend/node_modules/playwright`), Mermaid does not: it is
 * a documentation-only dependency, so install it where this script can find it and keep it out of
 * any manifest:
 *
 *   npm install --no-save --prefix frontend mermaid@11
 *
 * `MERMAID_ESM` overrides the path to `mermaid.esm.mjs`. The output is the diagram alone, with the
 * project's theme variables, so it can be embedded in a README and read without JavaScript.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function resolveIn(moduleName, bases) {
  for (const base of bases) {
    try {
      return require.resolve(moduleName, { paths: [base] });
    } catch {
      /* try the next location */
    }
  }
  return null;
}

function loadPlaywright() {
  const found = resolveIn("playwright", [path.join(ROOT, "frontend"), ROOT]);
  if (!found) throw new Error("playwright not found: run `npm install` in frontend/");
  return require(found);
}

function mermaidEsm() {
  if (process.env.MERMAID_ESM) return path.resolve(process.env.MERMAID_ESM);
  const found = resolveIn("mermaid/dist/mermaid.esm.mjs", [path.join(ROOT, "frontend"), ROOT]);
  if (!found) {
    throw new Error("mermaid not found: run `npm install --no-save --prefix frontend mermaid@11`");
  }
  return found;
}

async function main() {
  const [source, target] = process.argv.slice(2);
  if (!source || !target) {
    console.error("usage: render_mermaid.js <source.mmd> <target.svg>");
    return 2;
  }
  const definition = fs.readFileSync(path.resolve(source), "utf8");
  const { chromium } = loadPlaywright();
  // A page on `about:blank` has an opaque origin and cannot import a `file:` module; a page loaded
  // from disk can, with this flag, and nothing else is needed (no server, no bundler, no CDN).
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files"] });
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "bizview-mermaid-"));
  try {
    const host = path.join(scratch, "render.html");
    fs.writeFileSync(host, '<!doctype html><html><body><div id="out"></div></body></html>');
    const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    await page.goto("file://" + host);
    const esm = "file://" + mermaidEsm();
    const svg = await page.evaluate(async ({ definition, esm }) => {
      const mermaid = (await import(esm)).default;
      mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        sequence: { useMaxWidth: false, actorMargin: 46, messageMargin: 32 },
        themeVariables: {
          background: "#ffffff",
          primaryColor: "#eef2ff",
          primaryBorderColor: "#4f46e5",
          primaryTextColor: "#111827",
          lineColor: "#4b5563",
          textColor: "#111827",
          actorBkg: "#eef2ff",
          actorBorder: "#4f46e5",
          actorTextColor: "#111827",
          signalColor: "#374151",
          signalTextColor: "#111827",
        },
      });
      const { svg } = await mermaid.render("rendering", definition);
      return svg;
    }, { definition, esm });
    const out = path.resolve(target);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, svg.endsWith("\n") ? svg : svg + "\n", "utf8");
    console.log(`${path.relative(ROOT, out)}: ${svg.length} bytes`);
    return 0;
  } finally {
    await browser.close();
    fs.rmSync(scratch, { recursive: true, force: true });
  }
}

main().then((code) => process.exit(code), (error) => {
  console.error(error.message);
  process.exit(1);
});
