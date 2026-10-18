/** Feature 022 guard (FR-010, SC-002): English must have exactly the Spanish shape, with the same
 * placeholders, so a missing or stale translation fails the build. Functions are called with one
 * marker per parameter; both languages must use the same markers. */
import { describe, expect, it } from "vitest";
import { en } from "../../src/i18n/en";
import { es } from "../../src/i18n/es";

const mkMarker = (i: number) =>
  ({
    [Symbol.toPrimitive]: (hint: string) => (hint === "number" ? 7 : `⟦${i}⟧`),
    join: () => `⟦${i}⟧`,
    length: 2,
    toString: () => `⟦${i}⟧`,
  } as never);

const placeholdersIn = (s: string) =>
  new Set(Array.from(s.matchAll(/\{(\w+)\}/g), (m) => m[1]));

const markersIn = (s: string) =>
  new Set(Array.from(s.matchAll(/⟦(\d+)⟧/g), (m) => m[1]));

const sameSet = (a: Set<string>, b: Set<string>) =>
  a.size === b.size && Array.from(a).every((x) => b.has(x));

type Out = {
  keys: string[];
  kinds: string[];
  functions: string[];
  strings: string[];
  identity: string[];
};

const leafKind = (v: unknown): "string" | "function" | "array" | "object" | "other" => {
  if (typeof v === "string") return "string";
  if (typeof v === "function") return "function";
  if (Array.isArray(v)) return "array";
  if (v !== null && typeof v === "object") return "object";
  return "other";
};

function walk(a: unknown, b: unknown, path: string, out: Out): void {
  if (
    path !== "" &&
    a !== null &&
    typeof a === "object" &&
    b !== null &&
    typeof b === "object" &&
    a === b
  ) {
    out.identity.push(path);
    return;
  }

  const ka = leafKind(a);
  const kb = leafKind(b);

  if (ka !== kb) {
    out.kinds.push(`${path}: es ${ka}, en ${kb}`);
    return;
  }

  if (ka === "string") {
    const sa = a as string;
    const sb = b as string;
    if (sa.trim() === "" || sb.trim() === "") {
      out.strings.push(`${path}: empty`);
      return;
    }
    const pa = placeholdersIn(sa);
    const pb = placeholdersIn(sb);
    if (!sameSet(pa, pb)) {
      out.strings.push(`${path}: placeholders es ${sa} / en ${sb}`);
    }
    return;
  }

  if (ka === "function") {
    const fa = a as (...p: never[]) => unknown;
    const fb = b as (...p: never[]) => unknown;
    const na = fa.length;
    const nb = fb.length;
    if (na !== nb) {
      out.functions.push(`${path}: arity es ${na} / en ${nb}`);
      return;
    }

    const args = Array.from({ length: na }, (_, i) => mkMarker(i));
    let ra: unknown;
    let rb: unknown;
    let aThrew = false;
    let bThrew = false;

    try {
      ra = fa(...args);
    } catch {
      aThrew = true;
    }
    try {
      rb = fb(...args);
    } catch {
      bThrew = true;
    }

    if (aThrew || bThrew) {
      out.functions.push(`${path}: ${aThrew ? "es threw" : "en threw"}`);
      return;
    }

    if (
      typeof ra !== "string" ||
      typeof rb !== "string" ||
      (ra as string).trim() === "" ||
      (rb as string).trim() === ""
    ) {
      out.functions.push(`${path}: non-string or empty result`);
      return;
    }

    const ma = markersIn(ra as string);
    const mb = markersIn(rb as string);
    if (!sameSet(ma, mb)) {
      out.functions.push(`${path}: markers es ${ra} / en ${rb}`);
    }
    return;
  }

  if (ka === "array") {
    const aa = a as unknown[];
    const ab = b as unknown[];
    if (aa.length !== ab.length) {
      out.kinds.push(`${path}: array length es ${aa.length} / en ${ab.length}`);
      return;
    }
    for (let i = 0; i < aa.length; i++) {
      walk(aa[i], ab[i], `${path}[${i}]`, out);
    }
    return;
  }

  if (ka === "object") {
    const oa = a as Record<string, unknown>;
    const ob = b as Record<string, unknown>;
    const keysA = Object.keys(oa);
    const keysB = Object.keys(ob);
    for (const k of keysA) {
      const p = path ? `${path}.${k}` : k;
      if (!(k in ob)) {
        out.keys.push(`${p}: missing in en`);
      }
    }
    for (const k of keysB) {
      const p = path ? `${path}.${k}` : k;
      if (!(k in oa)) {
        out.keys.push(`${p}: extra in en`);
      }
    }
    for (const k of keysA) {
      if (k in ob) {
        const p = path ? `${path}.${k}` : k;
        walk(oa[k], ob[k], p, out);
      }
    }
    return;
  }
}

const OUT: Out = { keys: [], kinds: [], functions: [], strings: [], identity: [] };
walk(es, en, "", OUT);

describe("i18n catalogue parity (es/en)", () => {
  it("has the same key sets at every object level, including Record maps", () => {
    expect(OUT.keys).toEqual([]);
  });

  it("has the same leaf kinds and array lengths", () => {
    expect(OUT.kinds).toEqual([]);
  });

  it("has functions with the same arity and marker parity", () => {
    expect(OUT.functions).toEqual([]);
  });

  it("has non-empty strings with matching {name} placeholders", () => {
    expect(OUT.strings).toEqual([]);
  });

  it("does not reuse the same object identity between es and en sections", () => {
    expect(OUT.identity).toEqual([]);
  });
});
