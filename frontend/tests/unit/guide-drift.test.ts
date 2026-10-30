/** Feature 023 T042: the app guide never drifts from the app (routes, tiles, guards, links and
 * UI labels). Each failure names the item and the fix. */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { en } from "../../src/i18n/en";
import { es } from "../../src/i18n/es";
import { canAccess, matchRoute, ROUTES, type RouteAccess, type Viewer } from "../../src/lib/routeAccess";
import { ADMIN_TILES } from "../../src/pages/admin/adminTiles";

const ROOT = join(process.cwd(), "..");
const GUIDE = join(ROOT, "backend/app/guide");

interface Topic { id: string; roles: string[]; routes: string[]; tiles: string[] }
const index = parse(readFileSync(join(GUIDE, "index.yaml"), "utf8")) as { topics: Topic[] };
const LANGS = { es, en } as const;

/** Routes of App.tsx with the access their element guards: one route per line. */
function appRoutes(): Map<string, RouteAccess> {
  const lines = readFileSync(join(process.cwd(), "src/App.tsx"), "utf8").split("\n");
  const shellStart = lines.findIndex((l) => l.includes("<AppShell />") && l.includes("<Route element="));
  const routes = new Map<string, RouteAccess>();
  const redirects: [string, string][] = [];
  let depth = 0;
  lines.forEach((line, i) => {
    const m = line.match(/<Route\s+(index|path="([^"]+)")\s+element=\{(.*)\}\s*\/>/);
    if (i > shellStart && /<\/Route>/.test(line)) depth -= 1;
    if (i === shellStart) depth = 1;
    if (!m) return;
    const nested = shellStart >= 0 && i > shellStart && depth > 0;
    const raw = m[1] === "index" ? "" : (m[2] ?? "");
    const pattern = raw === "*" ? "*" : raw.startsWith("/") ? raw : `/${raw}`;
    const element = m[3];
    let access: RouteAccess = nested || element.includes("RequireAuth") ? "user" : "public";
    if (element.includes("RequireAdmin")) access = "admin";
    if (element.includes("RequireSuperuser")) access = "superuser";
    const redirect = element.match(/<Navigate to="([^"]+)"/);
    if (redirect) redirects.push([pattern, redirect[1]]);
    routes.set(pattern, access);
  });
  for (const [pattern, target] of redirects) routes.set(pattern, routes.get(target) ?? "user");
  return routes;
}

const VIEWERS: Record<string, Viewer | null> = {
  public: null,
  user: { role: "user", is_superuser: false },
  admin: { role: "admin", is_superuser: false },
  superuser: { role: "admin", is_superuser: true },
};

function catalogueLabels(catalogue: object): { values: Set<string>; prefixes: string[] } {
  const values = new Set<string>();
  const prefixes: string[] = [];
  const walk = (node: unknown) => {
    if (typeof node === "string") values.add(node.trim());
    else if (typeof node === "function") {
      const sentinel = "\u0000";
      try {
        const out = String((node as (...a: unknown[]) => unknown)(sentinel, sentinel, sentinel));
        const prefix = out.split(sentinel)[0].trim();
        if (prefix) prefixes.push(prefix);
        if (!out.includes(sentinel)) values.add(out.trim());
      } catch {
        /* functions that need real arguments have no static text to offer */
      }
    } else if (node && typeof node === "object") Object.values(node).forEach(walk);
  };
  walk(catalogue);
  return { values, prefixes };
}

const allowList = new Set(
  readFileSync(join(GUIDE, "labels-allow.txt"), "utf8")
    .split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#")),
);

function guideFiles(lang: "es" | "en"): [string, string][] {
  return readdirSync(join(GUIDE, lang))
    .filter((f) => f.endsWith(".md"))
    .map((f) => [f, readFileSync(join(GUIDE, lang, f), "utf8")]);
}

function stripCode(text: string): string {
  return text.replace(/```[\s\S]*?```/g, "").replace(/`[^`\n]*`/g, "");
}

describe("guide drift (feature 023)", () => {
  const app = appRoutes();
  const claimed = new Set(index.topics.flatMap((t) => t.routes));

  it("every App.tsx route has a topic and every topic route exists", () => {
    const missing = [...app.keys()].filter((r) => !claimed.has(r))
      .map((r) => `${r}: añade la ruta a \`routes\` de un tema en index.yaml`);
    const stale = [...claimed].filter((r) => !app.has(r))
      .map((r) => `${r}: no existe en App.tsx; quítala de index.yaml`);
    expect([...missing, ...stale]).toEqual([]);
  });

  it("every Administración tile has a topic", () => {
    const tiles = new Set(index.topics.flatMap((t) => t.tiles));
    expect(ADMIN_TILES.filter((tile) => !tiles.has(tile.to))
      .map((tile) => `${tile.to}: añade la tarjeta a \`tiles\` de su tema`)).toEqual([]);
  });

  it("routeAccess.ts mirrors App.tsx routes and guards", () => {
    const table = new Map(ROUTES.map((r) => [r.pattern, r.access]));
    const problems = [...app.entries()]
      .filter(([pattern, access]) => table.get(pattern) !== access)
      .map(([pattern, access]) => `${pattern}: routeAccess dice ${table.get(pattern)}, App.tsx ${access}`);
    problems.push(...[...table.keys()].filter((p) => !app.has(p))
      .map((p) => `${p}: está en routeAccess.ts pero no en App.tsx`));
    expect(problems).toEqual([]);
  });

  it("every app: link is a real route, without :param, openable by the topic's roles", () => {
    const roles = new Map(index.topics.map((t) => [t.id, t.roles]));
    const problems: string[] = [];
    for (const lang of ["es", "en"] as const) {
      for (const [file, text] of guideFiles(lang)) {
        const topicRoles = roles.get(file.replace(/\.md$/, "")) ?? ["superuser"];
        for (const m of text.matchAll(/\]\(app:([^)\s]*)\)/g)) {
          const to = m[1];
          const route = to.startsWith("/") ? matchRoute(to) : null;
          if (!route || to.includes(":")) problems.push(`${lang}/${file}: ${to} no es una ruta`);
          else if (!topicRoles.some((r) => canAccess(route.access, VIEWERS[r] ?? null)))
            problems.push(`${lang}/${file}: ${to} no lo abre ningún rol del tema (${topicRoles})`);
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it("every bold label is a catalogue label of its language or in labels-allow.txt", () => {
    const problems: string[] = [];
    for (const lang of ["es", "en"] as const) {
      const { values, prefixes } = catalogueLabels(LANGS[lang]);
      for (const [file, text] of guideFiles(lang)) {
        for (const m of stripCode(text).matchAll(/\*\*([^*\n]+)\*\*/g)) {
          const label = m[1].trim();
          if (values.has(label) || allowList.has(label) || prefixes.includes(label)) continue;
          problems.push(`${lang}/${file}: «${label}» no está en ${lang}.ts; usa el texto exacto ` +
            "de la pantalla o agrégalo a labels-allow.txt si no es una etiqueta");
        }
      }
    }
    expect(problems).toEqual([]);
  });
});
