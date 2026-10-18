import { describe, it, expect } from "vitest";
import {
  normalizeLocale,
  browserLocale,
  resolveLocale,
  intlTag,
} from "../../src/i18n/resolve";

describe("normalizeLocale", () => {
  it("returns null for empty or missing input", () => {
    expect(normalizeLocale()).toBeNull();
    expect(normalizeLocale(null)).toBeNull();
    expect(normalizeLocale("")).toBeNull();
    expect(normalizeLocale(undefined)).toBeNull();
  });

  it("returns es/en for primary subtags", () => {
    expect(normalizeLocale("es")).toBe("es");
    expect(normalizeLocale("en")).toBe("en");
    expect(normalizeLocale("es-ES")).toBe("es");
    expect(normalizeLocale("en-US")).toBe("en");
    expect(normalizeLocale("es_MX")).toBe("es");
    expect(normalizeLocale("EN")).toBe("en");
    expect(normalizeLocale(" Es ")).toBe("es");
  });

  it("returns null for unsupported locales", () => {
    expect(normalizeLocale("fr")).toBeNull();
    expect(normalizeLocale("de-DE")).toBeNull();
    expect(normalizeLocale("pt-BR")).toBeNull();
  });
});

describe("browserLocale", () => {
  it("returns the first supported locale", () => {
    expect(browserLocale(["en-US", "es-ES"])).toBe("en");
    expect(browserLocale(["es-MX", "fr-FR"])).toBe("es");
  });

  it("skips unsupported locales", () => {
    expect(browserLocale(["fr-FR", "de-DE", "en-GB"])).toBe("en");
  });

  it("returns null if none supported", () => {
    expect(browserLocale(["fr-FR", "de-DE"])).toBeNull();
    expect(browserLocale([])).toBeNull();
  });
});

describe("resolveLocale", () => {
  it("account preference wins", () => {
    expect(resolveLocale({ account: "en", device: "es", languages: ["es-ES"], defaultLocale: "es" }))
      .toBe("en");
  });

  it("device cache wins when no account preference", () => {
    expect(resolveLocale({ account: null, device: "es", languages: ["en-US"], defaultLocale: "en" }))
      .toBe("es");
  });

  it("browser languages next", () => {
    expect(resolveLocale({ account: null, device: null, languages: ["en-US", "es-ES"], defaultLocale: "es" }))
      .toBe("en");
  });

  it("default locale next", () => {
    expect(resolveLocale({ account: null, device: null, languages: [], defaultLocale: "en" })).toBe("en");
  });

  it("falls back to es when nothing provided", () => {
    expect(resolveLocale({ account: null, device: null, languages: [], defaultLocale: null })).toBe("es");
  });

  it("ignores unsupported values in each stage", () => {
    expect(resolveLocale({ account: null, device: "fr", languages: ["de-DE"], defaultLocale: "pt" }))
      .toBe("es");
  });
});

describe("intlTag", () => {
  it("returns es-ES for es", () => {
    expect(intlTag("es")).toBe("es-ES");
  });

  it("returns en-US for en", () => {
    expect(intlTag("en")).toBe("en-US");
  });
});
