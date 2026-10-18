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
    const match = sourceText.match(/AUDIT_KINDS\s*=\s*\((.*?)\)/s);
    expect(match, "AUDIT_KINDS tuple not found in models.py").not.toBeNull();

    const kindMatches = match![1].matchAll(/"([a-z0-9_]+)"/g);
    const backendKinds = new Set<string>();
    for (const m of kindMatches) {
      backendKinds.add(m[1]);
    }

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
