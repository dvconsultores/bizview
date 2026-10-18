import { describe, expect, it } from "vitest";
import { generatePassword, passwordChecklist, passwordProblem } from "../../src/lib/password";

describe("passwordProblem mirrors the server rules", () => {
  it.each([
    ["short", "ana@example.com", undefined, "too_short"],
    ["x".repeat(129), "ana@example.com", undefined, "too_long"],
    ["ANA@example.com", "ana@example.com", undefined, "contains_email"],
    ["xx-anabel-2024", "anabel@example.com", undefined, "contains_email"],
    ["Same-password-1", "ana@example.com", "Same-password-1", "same_as_current"],
    ["Good-password-1", "ana@example.com", undefined, null],
    ["ana-is-fine-123", "an@example.com", undefined, null], // local part < 3 chars is not checked
  ])("%s / %s", (pw, email, current, expected) => {
    expect(passwordProblem(pw, email, current)).toBe(expected);
  });
});

describe("generatePassword", () => {
  it("creates passwords that satisfy the rules", () => {
    for (let i = 0; i < 50; i++) {
      const pw = generatePassword();
      expect(pw).toHaveLength(14);
      expect(passwordProblem(pw, "someone@example.com")).toBeNull();
    }
  });
});

describe("passwordChecklist", () => {
  it("reports each rule", () => {
    expect(passwordChecklist("", "a@b.co").every((c) => !c.ok)).toBe(true);
    expect(passwordChecklist("Good-password-1", "ana@example.com", "old").every((c) => c.ok)).toBe(true);
  });
});
