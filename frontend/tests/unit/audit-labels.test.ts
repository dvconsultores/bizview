/**
 * Feature 022 guard (T022, US2 AC5): every audit event kind the backend can
 * record has a label in both languages.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { es } from "../../src/i18n/es";
import { en } from "../../src/i18n/en";

const MODELS = join(process.cwd(), "..", "backend", "app", "models.py");

describe.skipIf(!existsSync(MODELS))("audit event kind labels", () => {
  it("has a label for every backend audit kind, and no stale label keys", () => {
    const sourceText = readFileSync(MODELS, "utf8");
    // Two catalogues (hotfix 045-audit): what the product writes, and what the database may still
    // hold from before 045. Both must be labelled — history is readable — but only the first is
    // emittable, and that distinction stays in the backend.
    const kindsOf = (name: string): Set<string> => {
      // `AUDIT_KINDS = (` and `HISTORICAL_AUDIT_KINDS: tuple[str, ...] = (` both count.
      const match = sourceText.match(
        new RegExp(`${name}(?:\\s*:\\s*[^=]+)?\\s*=\\s*\\((.*?)\\)`, "s"),
      );
      expect(match, `${name} tuple not found in models.py`).not.toBeNull();
      return new Set([...match![1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]));
    };
    const writable = kindsOf("AUDIT_KINDS");
    const historical = kindsOf("HISTORICAL_AUDIT_KINDS");
    expect([...historical].filter((kind) => writable.has(kind))).toEqual([]);
    const backendKinds = new Set([...writable, ...historical]);

    // The backend catalogue is stable; guard against accidentally deleting most entries.
    expect(backendKinds.size).toBeGreaterThanOrEqual(60);

    const esLabels = (es.audit ?? {}) as Record<string, string>;
    const enLabels = (en.audit ?? {}) as Record<string, string>;

    const missingEs = [...backendKinds].filter((kind) => !esLabels[kind]?.trim());
    const missingEn = [...backendKinds].filter((kind) => !enLabels[kind]?.trim());

    expect(missingEs, `Missing Spanish audit labels: ${missingEs.join(", ")}`).toEqual([]);
    expect(missingEn, `Missing English audit labels: ${missingEn.join(", ")}`).toEqual([]);

    const staleEs = Object.keys(esLabels).filter((key) => !backendKinds.has(key));
    const staleEn = Object.keys(enLabels).filter((key) => !backendKinds.has(key));

    expect(staleEs, `Stale Spanish audit label keys: ${staleEs.join(", ")}`).toEqual([]);
    expect(staleEn, `Stale English audit label keys: ${staleEn.join(", ")}`).toEqual([]);
  });
});
