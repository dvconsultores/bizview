import { describe, expect, it } from "vitest";
import { ApiError } from "../../src/api/client";
import {
  domainAllowed,
  emailDomain,
  errorText,
  hourLabel,
  isValidEmail,
  scheduleText,
  selectionPayload,
} from "../../src/lib/sharing";
import { t } from "../../src/i18n/es";

describe("selectionPayload", () => {
  it("keeps from/to only for custom periods", () => {
    expect(
      selectionPayload({
        period: "custom",
        from: "2026-01-01",
        to: "2026-01-31",
        compare: "none",
        filters: {},
      }),
    ).toEqual({
      period: "custom",
      compare: "none",
      from: "2026-01-01",
      to: "2026-01-31",
    });
    expect(
      selectionPayload({
        period: "last_month",
        from: "2026-01-01",
        to: "2026-01-31",
        compare: "none",
        filters: {},
      }),
    ).toEqual({ period: "last_month", compare: "none" });
  });

  it("maps non-empty filters to filter.<id> and omits empty ones", () => {
    expect(
      selectionPayload({
        period: "last_month",
        from: "",
        to: "",
        compare: "previous_period",
        filters: { brand: ["Acme", "Nova"], region: [] },
      }),
    ).toEqual({
      period: "last_month",
      compare: "previous_period",
      "filter.brand": ["Acme", "Nova"],
    });
  });
});

describe("isValidEmail", () => {
  it("accepts valid addresses", () => {
    expect(isValidEmail("ana@acme.com")).toBe(true);
    expect(isValidEmail("A.B@sub.acme.co")).toBe(true);
    expect(isValidEmail("  ana@acme.com  ")).toBe(true);
  });

  it("rejects invalid addresses", () => {
    expect(isValidEmail("")).toBe(false);
    expect(isValidEmail("ana")).toBe(false);
    expect(isValidEmail("ana@acme")).toBe(false);
    expect(isValidEmail("a b@acme.com")).toBe(false);
    expect(isValidEmail("ana@@acme.com")).toBe(false);
    expect(isValidEmail("ana@acme.c")).toBe(false);
  });
});

describe("emailDomain", () => {
  it("returns the lowercase part after the last @", () => {
    expect(emailDomain("Ana@Acme.COM")).toBe("acme.com");
    expect(emailDomain("sin-arroba")).toBe("");
  });
});

describe("domainAllowed", () => {
  it("compares domains case-insensitively", () => {
    expect(domainAllowed("luis@Acme.com", ["acme.com"])).toBe(true);
    expect(domainAllowed("luis@other.com", ["acme.com"])).toBe(false);
    expect(domainAllowed("luis@acme.com", [])).toBe(false);
  });
});

describe("hourLabel", () => {
  it("pads hours", () => {
    expect(hourLabel(8)).toBe("08:00");
    expect(hourLabel(23)).toBe("23:00");
  });
});

describe("scheduleText", () => {
  it("renders each frequency", () => {
    expect(
      scheduleText({
        frequency: "daily",
        hour: 8,
        weekday: null,
        monthday: null,
      }),
    ).toBe(t.sharing.schedules.everyDay("08:00"));
    expect(
      scheduleText({
        frequency: "weekly",
        hour: 9,
        weekday: 0,
        monthday: null,
      }),
    ).toBe(t.sharing.schedules.everyWeek("lunes", "09:00"));
    expect(
      scheduleText({
        frequency: "monthly",
        hour: 10,
        weekday: null,
        monthday: 5,
      }),
    ).toBe(t.sharing.schedules.everyMonth(5, "10:00"));
  });
});

describe("errorText", () => {
  it("uses ApiError.message and falls back to unexpected", () => {
    expect(
      errorText(new ApiError(404, "not_found", "No existe")),
    ).toBe("No existe");
    expect(errorText(new Error("red"))).toBe(t.common.unexpected);
  });
});
