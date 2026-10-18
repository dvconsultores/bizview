import { describe, expect, it } from "vitest";
import { localized } from "../../src/lib/labels";

describe("localized", () => {
  it("returns the _en value when locale is en and it is non-empty", () => {
    const obj = { title: "Título", title_en: "Title" };
    expect(localized(obj, "title", "en")).toBe("Title");
  });

  it("returns the base value when _en is blank", () => {
    const obj = { title: "Título", title_en: "   " };
    expect(localized(obj, "title", "en")).toBe("Título");
  });

  it("ignores _en when locale is es", () => {
    const obj = { title: "Título", title_en: "Title" };
    expect(localized(obj, "title", "es")).toBe("Título");
  });

  it("returns undefined for null object", () => {
    expect(localized(null, "title", "en")).toBeUndefined();
  });

  it("works for nested label object", () => {
    const obj = { label: "Etiqueta", label_en: "Label" };
    expect(localized(obj, "label", "en")).toBe("Label");
  });
});
