/** Mirror of the server password rules (backend/app/auth/passwords.py) for instant feedback.
 * The server stays authoritative. */
export const MIN_LEN = 10;
export const MAX_LEN = 128;

export type PasswordProblem = "too_short" | "too_long" | "contains_email" | "same_as_current";

export function passwordProblem(
  password: string,
  email: string,
  current?: string,
): PasswordProblem | null {
  if (password.length < MIN_LEN) return "too_short";
  if (password.length > MAX_LEN) return "too_long";
  const e = email.trim().toLowerCase();
  const local = e.split("@")[0] ?? "";
  const lowered = password.toLowerCase();
  if (lowered === e || (local.length >= 3 && lowered.indexOf(local) !== -1)) return "contains_email";
  if (current !== undefined && password === current) return "same_as_current";
  return null;
}

export interface RuleCheck {
  id: string;
  ok: boolean;
}

/** Live checklist shown next to password fields. */
export function passwordChecklist(password: string, email: string, current?: string): RuleCheck[] {
  const e = email.trim().toLowerCase();
  const local = e.split("@")[0] ?? "";
  const lowered = password.toLowerCase();
  const checks: RuleCheck[] = [
    { id: "length", ok: password.length >= MIN_LEN && password.length <= MAX_LEN },
    {
      id: "email",
      ok: password.length > 0 && lowered !== e && !(local.length >= 3 && lowered.indexOf(local) !== -1),
    },
  ];
  if (current !== undefined) checks.push({ id: "different", ok: password.length > 0 && password !== current });
  return checks;
}

/** Random temporary password: 14 chars from an unambiguous alphabet, crypto-random. */
export function generatePassword(length = 14): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!#%+=?";
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  let out = "";
  for (let i = 0; i < length; i++) out += alphabet[bytes[i] % alphabet.length];
  return out;
}
