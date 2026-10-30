/**
 * 043 WS-A: remove the `assistant` and `chatAttachments` groups from both catalogues.
 *
 * Run once, then delete this file. It refuses to delete a group that any remaining file still
 * reads, so a forgotten edit fails loudly instead of turning into a blank string in the UI.
 *
 *   node scripts/prune_i18n_043.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const GROUPS = ["assistant", "chatAttachments"];

/** Index just past the `}` that closes the `{` at `start`. String- and comment-aware. */
function matchingBrace(text, start) {
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === "/" && next === "/") {
      i = text.indexOf("\n", i);
      if (i === -1) return -1;
      continue;
    }
    if (ch === "/" && next === "*") {
      i = text.indexOf("*/", i + 2);
      if (i === -1) return -1;
      i += 1;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === "`") {
      const quote = ch;
      for (i += 1; i < text.length; i++) {
        if (text[i] === "\\") { i += 1; continue; }
        if (text[i] === quote) break;
      }
      continue;
    }
    if (ch === "{") depth += 1;
    if (ch === "}") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function removeGroup(text, group) {
  const marker = `\n  ${group}: {`;
  const at = text.indexOf(marker);
  if (at === -1) return { text, removed: false };
  const open = text.indexOf("{", at);
  const close = matchingBrace(text, open);
  if (close === -1) throw new Error(`unbalanced brace after ${group}`);
  let end = close + 1;
  if (text[end] === ",") end += 1;
  if (text[end] === "\n") end += 1;
  return { text: text.slice(0, at) + text.slice(end), removed: true };
}

function references(group) {
  try {
    const out = execSync(
      `grep -rn "t\\.${group}\\.\\|\\.${group}\\.\\[" src --include=*.ts --include=*.tsx || true`,
      { cwd: ROOT, encoding: "utf8" },
    );
    return out.trim();
  } catch {
    return "";
  }
}

let failed = false;
for (const group of GROUPS) {
  const hits = references(group);
  if (hits) {
    console.error(`\n${group}: still referenced, refusing to delete:\n${hits}`);
    failed = true;
  }
}
if (failed) process.exit(1);

for (const name of ["es", "en"]) {
  const path = join(ROOT, "src", "i18n", `${name}.ts`);
  let text = readFileSync(path, "utf8");
  const removed = [];
  for (const group of GROUPS) {
    const result = removeGroup(text, group);
    text = result.text;
    if (result.removed) removed.push(group);
  }
  writeFileSync(path, text);
  console.log(`${name}.ts: removed ${removed.join(", ") || "nothing"}`);
}
