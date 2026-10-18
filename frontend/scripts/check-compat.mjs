// Fails the build when the bundle uses APIs missing in Safari/iOS 14 (research R8).
// Syntax is already lowered by Vite's build.target; this catches runtime APIs, which are not.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const DIR = "dist/assets";
const RULES = [
  [/\bstructuredClone\(/, "structuredClone (Safari 15.4)"],
  [/\bObject\.hasOwn\(/, "Object.hasOwn (Safari 15.4)"],
  [/\.findLast(Index)?\(/, "Array#findLast (Safari 15.4)"],
  [/\.replaceAll\(/, "String#replaceAll (Safari 13.1 ok, but not in some Android 8 WebViews)"],
  [/\.at\((-?\d+|[a-zA-Z_$][\w$]*)\)/, "Array#at / String#at (Safari 15.4) — verify"],
  [/\bcrypto\.randomUUID\(/, "crypto.randomUUID (Safari 15.4)"],
  [/:has\(/, "CSS :has() (Safari 15.4)"],
  [/\bcolor-mix\(/, "CSS color-mix() (Safari 16.2)"],
  [/@container\b/, "CSS container queries (Safari 16)"],
];
// Known-safe occurrences inside libraries.
const ALLOW = [
  "`lossy`in t", // @ungap/structured-clone: uses structuredClone only when it exists
  "`@color-profile`,`@container`", // CodeMirror CSS: at-rule names as strings, not CSS
];
// Rules covered by src/polyfills.ts, skipped only while main.tsx imports it first.
const POLYFILLED = /^import "\.\/polyfills";/.test(readFileSync("src/main.tsx", "utf8"))
  ? new Set(["Object.hasOwn (Safari 15.4)", "Array#at / String#at (Safari 15.4) — verify"])
  : new Set();

let failures = 0;
for (const file of readdirSync(DIR)) {
  if (!/\.(js|css)$/.test(file)) continue;
  const src = readFileSync(join(DIR, file), "utf8");
  for (const [re, name] of RULES) {
    if (POLYFILLED.has(name)) continue;
    const g = new RegExp(re.source, "g");
    let m;
    while ((m = g.exec(src))) {
      const ctx = src.slice(Math.max(0, m.index - 60), m.index + 40).replace(/\s+/g, " ");
      if (ALLOW.some((a) => ctx.includes(a))) continue;
      console.error(`${file}: ${name}\n   …${ctx}…`);
      failures++;
    }
  }
}
if (failures) {
  console.error(`\n${failures} compatibility finding(s).`);
  process.exit(1);
}
console.log("compat: OK (no Safari 14-incompatible APIs found)");
