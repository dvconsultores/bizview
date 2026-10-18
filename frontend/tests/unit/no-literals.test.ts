/**
 * Feature 022 guard (FR-010, FR-011, US3 AC1): user-visible text comes from the
 * catalogues so every screen works in Spanish and English.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");

/**
 * Exact trimmed text → reason for the global allow-list.
 */
const ALLOWED_TEXT: Record<string, string> = {
  BizView: "brand name",
  "Bizview AI Powered": "brand name",
  PDF: "technical format",
  CSV: "technical format",
  SQL: "technical format",
  JSON: "technical format",
  YAML: "technical format",
  URL: "technical term",
  API: "technical term",
  MFA: "technical term",
  SMTP: "technical term",
  Telegram: "integration name",
  OpenAI: "integration name",
  PostgreSQL: "database name",
  REST: "technical term",
  ID: "technical term",
  OK: "technical term",
  "AGPL-3.0-or-later": "licence identifier",
  Español: "language name shown in its own language",
  English: "language name shown in its own language",
};

/**
 * Per-file allow-list: exact trimmed texts allowed in one file.
 * Add entries with a comment explaining the reason.
 */
const ALLOWED_BY_FILE: Record<string, string[]> = {};

/**
 * Technical tokens that are not user-visible prose: env-var/constant names,
 * identifiers/paths/urls/file names with no spaces, and digit/punctuation values with an optional unit.
 * A word followed by a colon ("Versión:") is a label, not a token.
 */
function isTechnical(text: string): boolean {
  const t = text.trim();
  if (/^[A-Z][A-Z0-9_]{2,}$/.test(t)) return true;
  if (!/\s/.test(t) && /[A-Za-z0-9]/.test(t) && /_|\/|@|=|--|:\/\/|\w\.\w/.test(t)) return true;
  if (/^[\d.,;:%+\-()[\]{}<>/\\]+(px|ms|KB|MB|GB|s|em|rem|%)?$/i.test(t)) return true;
  return false;
}

function isAllowed(file: string, text: string): boolean {
  const t = text.trim();
  const rel = file;
  if (ALLOWED_TEXT[t] !== undefined) return true;
  if (isTechnical(t)) return true;
  const perFile = ALLOWED_BY_FILE[rel];
  if (perFile && perFile.includes(t)) return true;
  return false;
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) {
      if (p.replaceAll("\\", "/").includes("/i18n/")) return [] as string[];
      return sourceFiles(p);
    }
    if (!/\.tsx?$/.test(f) || /\.d\.ts$/.test(f)) return [] as string[];
    if (p.replaceAll("\\", "/").includes("/i18n/")) return [] as string[];
    return [p];
  });
}

/**
 * Spanish UI words without accents (feature 022 T051): a returned value or a branch of a
 * conditional that contains one of them is user-visible text the accent check cannot see
 * ("ahora", `${n} activos`, "1 fuente"). Single-word ids ("fuente", "borrador") are not flagged.
 */
const SPANISH_WORDS = /\b(ahora|hoy|ayer|activos?|activas?|conectad[ao]s?|fuentes?|filas?|tableros?|reportes?|usuarios?|proyectos?|cargando|todav[ií]a|nuev[ao]s?)\b/i;
const SPANISH_TIME_WORDS = new Set(["ahora", "hoy", "ayer"]);

function inValuePosition(node: ts.Node): boolean {
  let p = node.parent;
  while (p && ts.isParenthesizedExpression(p)) p = p.parent;
  return !!p && (ts.isReturnStatement(p) || ts.isConditionalExpression(p)
    || (ts.isArrowFunction(p) && p.body === node)
    || (ts.isBinaryExpression(p) && p.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken));
}

function spanishValue(node: ts.Node, text: string, isTemplate: boolean): boolean {
  const t = text.trim();
  if (/^[/?#]/.test(t) || /:\/\//.test(t)) return false;          // routes and URLs
  if (!inValuePosition(node) || !SPANISH_WORDS.test(t)) return false;
  return isTemplate || /\s/.test(t) || SPANISH_TIME_WORDS.has(t.toLowerCase());
}

interface Findings {
  text: string[];
  attrs: string[];
  spanish: string[];
  imports: string[];
  hook: string[];
  eager: string[];
  titles: string[];
  memo: string[];
  locales: string[];
}

const ATTR_NAMES = new Set([
  "aria-label",
  "aria-description",
  "aria-roledescription",
  "aria-valuetext",
  "title",
  "placeholder",
  "alt",
  "label",
  "hint",
  "description",
  "emptyText",
  "confirmLabel",
  "cancelLabel",
  "subtitle",
  "text",
]);

function scan(file: string): Findings {
  const source = readFileSync(file, "utf8");
  const sf = ts.createSourceFile(
    file,
    source,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const rel = relative(SRC, file).replaceAll("\\", "/");
  const out: Findings = {
    text: [],
    attrs: [],
    spanish: [],
    imports: [],
    hook: [],
    eager: [],
    titles: [],
    memo: [],
    locales: [],
  };
  let usesT = false;
  const line = (node: ts.Node): number =>
    sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
  const off = (list: string[], node: ts.Node, text: string): void => {
    list.push(`${rel}:${line(node)} ${JSON.stringify(text.slice(0, 60))}`);
  };

  function isInsideFunction(node: ts.Node): boolean {
    let p: ts.Node | undefined = node.parent;
    while (p) {
      if (ts.isFunctionLike(p)) return true;
      if (ts.isSourceFile(p)) break;
      p = p.parent;
    }
    return false;
  }

  function isTopLevelStatement(node: ts.Node): boolean {
    return node.parent === sf;
  }

  function isShadowed(node: ts.Node): boolean {
    let current: ts.Node | undefined = node;
    while (current && current !== sf) {
      if (ts.isFunctionLike(current)) {
        for (const param of current.parameters) {
          if (ts.isIdentifier(param.name) && param.name.text === "t") {
            return true;
          }
          if (
            ts.isObjectBindingPattern(param.name) ||
            ts.isArrayBindingPattern(param.name)
          ) {
            for (const element of param.name.elements) {
              if (ts.isOmittedExpression(element)) continue;
              if (ts.isIdentifier(element.name) && element.name.text === "t") {
                return true;
              }
              if (
                ts.isObjectBindingPattern(element.name) ||
                ts.isArrayBindingPattern(element.name)
              ) {
                const bindings = element.name.elements;
                for (const binding of bindings) {
                  if (ts.isOmittedExpression(binding)) continue;
                  if (ts.isIdentifier(binding.name) && binding.name.text === "t") {
                    return true;
                  }
                }
              }
            }
          }
        }
      }
      if (ts.isBlock(current) || ts.isCaseClause(current)) {
        for (const statement of current.statements) {
          if (ts.isVariableStatement(statement)) {
            for (const declaration of statement.declarationList.declarations) {
              if (ts.isIdentifier(declaration.name)) {
                if (
                  declaration.name.text === "t" &&
                  !(
                    declaration.initializer &&
                    ts.isCallExpression(declaration.initializer) &&
                    ts.isIdentifier(declaration.initializer.expression) &&
                    declaration.initializer.expression.text === "useT"
                  )
                ) {
                  return true;
                }
              } else if (
                ts.isObjectBindingPattern(declaration.name) ||
                ts.isArrayBindingPattern(declaration.name)
              ) {
                for (const element of declaration.name.elements) {
                  if (ts.isOmittedExpression(element)) continue;
                  if (ts.isIdentifier(element.name) && element.name.text === "t") {
                    return true;
                  }
                  if (
                    ts.isObjectBindingPattern(element.name) ||
                    ts.isArrayBindingPattern(element.name)
                  ) {
                    for (const binding of element.name.elements) {
                      if (ts.isOmittedExpression(binding)) continue;
                      if (ts.isIdentifier(binding.name) && binding.name.text === "t") {
                        return true;
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
      if (
        ts.isForStatement(current) ||
        ts.isForOfStatement(current) ||
        ts.isForInStatement(current)
      ) {
        const initializer = current.initializer;
        if (initializer && ts.isVariableDeclarationList(initializer)) {
          for (const declaration of initializer.declarations) {
            if (ts.isIdentifier(declaration.name)) {
              if (
                declaration.name.text === "t" &&
                !(
                  declaration.initializer &&
                  ts.isCallExpression(declaration.initializer) &&
                  ts.isIdentifier(declaration.initializer.expression) &&
                  declaration.initializer.expression.text === "useT"
                )
              ) {
                return true;
              }
            } else if (
              ts.isObjectBindingPattern(declaration.name) ||
              ts.isArrayBindingPattern(declaration.name)
            ) {
              for (const element of declaration.name.elements) {
                if (ts.isOmittedExpression(element)) continue;
                if (ts.isIdentifier(element.name) && element.name.text === "t") {
                  return true;
                }
                if (
                  ts.isObjectBindingPattern(element.name) ||
                  ts.isArrayBindingPattern(element.name)
                ) {
                  for (const binding of element.name.elements) {
                    if (ts.isOmittedExpression(binding)) continue;
                    if (ts.isIdentifier(binding.name) && binding.name.text === "t") {
                      return true;
                    }
                  }
                }
              }
            }
          }
        }
      }
      current = current.parent;
    }
    return false;
  }

  function isCatalogueT(n: ts.Node): boolean {
    return (
      ts.isPropertyAccessExpression(n) &&
      ts.isIdentifier(n.expression) &&
      n.expression.text === "t" &&
      !isShadowed(n)
    );
  }

  // Text inside code elements is a technical token (command, file or folder name).
  const CODE_TAGS = new Set(["CodeChip", "code", "kbd", "pre"]);
  function inCodeElement(node: ts.JsxText): boolean {
    const parent = node.parent;
    return ts.isJsxElement(parent) && CODE_TAGS.has(parent.openingElement.tagName.getText(sf));
  }
  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node) && !inCodeElement(node)) {
      const text = node.getText(sf);
      if (/\p{L}{2,}/u.test(text.trim())) {
        if (!isAllowed(rel, text.trim())) {
          off(out.text, node, text.trim());
        }
      }
    } else if (ts.isStringLiteralLike(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      const text = node.text;
      if (/[áéíóúñÁÉÍÓÚÑ¿¡ü]/.test(text) || spanishValue(node, text, false)) {
        off(out.spanish, node, text);
      }
    } else if (ts.isTemplateExpression(node)) {
      const full = node.getText(sf);
      const literal = [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(" ");
      if (/[áéíóúñÁÉÍÓÚÑ¿¡ü]/.test(full) || spanishValue(node, literal, true)) {
        const text = full.slice(1, full.length - 1);
        off(out.spanish, node, text);
      }
    }

    if (ts.isJsxAttribute(node)) {
      const name = node.name.getText(sf);
      if (ATTR_NAMES.has(name)) {
        const init = node.initializer;
        if (init) {
          let value: string | undefined;
          if (ts.isStringLiteral(init)) value = init.text;
          else if (ts.isJsxExpression(init)) {
            const expr = init.expression;
            if (expr && (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr))) {
              value = expr.text;
            }
          }
          if (value !== undefined && /\p{L}{2,}/u.test(value.trim())) {
            if (!isAllowed(rel, value.trim())) {
              off(out.attrs, node, value.trim());
            }
          }
        }
      }
    }

    if (ts.isImportDeclaration(node) || ts.isImportEqualsDeclaration(node)) {
      try {
        const spec = node.moduleSpecifier.getText(sf).replace(/["']/g, "");
        if (spec.endsWith("i18n/es") || spec.endsWith("i18n/en")) {
          out.imports.push(`${rel}:${line(node)} ${JSON.stringify(spec)}`);
        }
      } catch {
        /* ignore malformed */
      }
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const arg = node.arguments[0];
      if (arg && ts.isStringLiteralLike(arg)) {
        const spec = arg.text;
        if (spec.endsWith("i18n/es") || spec.endsWith("i18n/en")) {
          out.imports.push(`${rel}:${line(node)} ${JSON.stringify(spec)}`);
        }
      }
    }

    if (isCatalogueT(node)) usesT = true;

    if (isTopLevelStatement(node)) {
      if (ts.isVariableStatement(node) || ts.isExportAssignment(node)) {
        let hasT = false;
        const checkNode = (n: ts.Node): void => {
          if (isCatalogueT(n) && !isInsideFunction(n)) {
            hasT = true;
          }
          ts.forEachChild(n, checkNode);
        };
        checkNode(node);
        if (hasT) {
          off(out.eager, node, "t. used at module level");
        }
      }
    }

    // FR-004: Intl constructors and toLocale*String calls take the active locale from src/lib/intl.ts.
    if ((ts.isNewExpression(node) || ts.isCallExpression(node)) && node.arguments && node.arguments.length > 0) {
      const callee = node.expression.getText(sf);
      const first = node.arguments[0];
      if (/^Intl\.|\.toLocale(Date|Time)?String$/.test(callee) && ts.isStringLiteralLike(first)) {
        off(out.locales, node, `${callee}("${first.text}")`);
      }
    }
    if (ts.isCallExpression(node)) {
      const callee = node.expression;
      const isMemoCallback =
        ts.isIdentifier(callee) &&
        (callee.text === "useMemo" || callee.text === "useCallback");
      const isReactMemoCallback =
        ts.isPropertyAccessExpression(callee) &&
        ts.isIdentifier(callee.expression) &&
        callee.expression.text === "React" &&
        (callee.name.text === "useMemo" || callee.name.text === "useCallback");
      if ((isMemoCallback || isReactMemoCallback) &&
        node.arguments.length >= 2 &&
        (ts.isArrowFunction(node.arguments[0]) || ts.isFunctionExpression(node.arguments[0])) &&
        ts.isArrayLiteralExpression(node.arguments[1])) {
        const readsT = (n: ts.Node): boolean => isCatalogueT(n) || (ts.forEachChild(n, readsT) ?? false);
        if (
          readsT(node.arguments[0]) &&
          !node.arguments[1].elements.some((e) => ts.isIdentifier(e) && e.text === "t")
        ) {
          off(out.memo, node, "useMemo/useCallback reads t but t is not in deps");
        }
      }
    }
    if (ts.isBinaryExpression(node)) {
      const op = node.operatorToken.kind;
      if (op === ts.SyntaxKind.EqualsToken) {
        const left = node.left;
        if (
          ts.isPropertyAccessExpression(left) &&
          left.expression.kind === ts.SyntaxKind.Identifier &&
          (left.expression as ts.Identifier).text === "document" &&
          left.name.text === "title"
        ) {
          let hasT = false;
          const checkNode = (n: ts.Node): void => {
            if (isCatalogueT(n)) {
              hasT = true;
            }
            ts.forEachChild(n, checkNode);
          };
          checkNode(node.right);
          if (hasT) {
            off(out.titles, node, "document.title uses t.");
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  };

  visit(sf);
  if (file.endsWith(".tsx") && usesT && !/\buseT\s*\(/.test(source)) out.hook.push(rel);
  return out;
}

const RESULTS = sourceFiles(SRC).map(scan);

function merge(pick: (r: Findings) => string[]): string[] {
  return RESULTS.flatMap(pick);
}

describe("i18n no-literals guard", () => {
  it("has no raw JSX text with letters", () => {
    expect(
      merge((r) => r.text),
      "move user-visible text to src/i18n/es.ts and en.ts (feature 022 recipe)",
    ).toEqual([]);
  });

  it("has no unlocalized user-visible JSX attributes", () => {
    expect(
      merge((r) => r.attrs),
      "move user-visible text to src/i18n/es.ts and en.ts (feature 022 recipe)",
    ).toEqual([]);
  });

  it("has no Spanish-letter literals outside src/i18n", () => {
    expect(
      merge((r) => r.spanish),
      "move user-visible text to src/i18n/es.ts and en.ts (feature 022 recipe)",
    ).toEqual([]);
  });

  it("does not import i18n/es or i18n/en outside src/i18n", () => {
    expect(
      merge((r) => r.imports),
      "import { useT } from the i18n index (components) or { t } from i18n/live (helpers)",
    ).toEqual([]);
  });

  it("calls useT() whenever t.* is used in a .tsx file", () => {
    expect(
      merge((r) => r.hook),
      "call const t = useT() in the component so it re-renders on a language switch",
    ).toEqual([]);
  });

  it("does not eagerly capture t.* at module level", () => {
    expect(
      merge((r) => r.eager),
      "compute catalogue text at render time (function of t), not at import",
    ).toEqual([]);
  });

  it("does not set document.title from t.*", () => {
    expect(
      merge((r) => r.titles),
      "document titles carry brand/dashboard names only",
    ).toEqual([]);
  });

  it("lists t in the deps of useMemo/useCallback that read the catalogue", () => {
    expect(
      merge((r) => r.memo),
      "add t to the dependency array so the value follows a language switch",
    ).toEqual([]);
  });

  it("formats with the active locale, not a hard-coded tag", () => {
    expect(
      merge((r) => r.locales)
    ).toEqual([]);
  });
});
