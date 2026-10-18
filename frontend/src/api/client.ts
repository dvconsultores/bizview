/** Fetch wrapper for the same-origin JSON API (contracts/api.md). */
import { currentLocale, t } from "../i18n/live";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string> = {},
    public retryAfter?: number,
    /** The whole error object of the response (extra keys such as `specs`, `commands`). */
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

type Json = Record<string, unknown> | unknown[];

async function request<T>(method: string, path: string, body?: Json, retried = false): Promise<T> {
  // Feature 022 FR-005: the backend renders `message` in this language.
  const headers: Record<string, string> = { Accept: "application/json", "Accept-Language": currentLocale() };
  if (method !== "GET") headers["X-Requested-With"] = "fetch";
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network", t.errors.network);
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const e = data?.error ?? {};
    const err = new ApiError(
      res.status,
      e.code ?? "error",
      e.message ?? t.common.unexpected,
      e.fields ?? {},
      e.retry_after_seconds,
      e,
    );
    if (res.status === 401 && err.code === "unauthenticated") onUnauthenticated(err);
    // Step-up (feature 004): ask for the password once, then retry the same request.
    if (res.status === 403 && err.code === "reauth_required" && !retried && reauthHandler) {
      if (await reauthHandler()) return request<T>(method, path, body, true);
    }
    if (res.status === 403 && err.code === "mfa_enrollment_required") mfaEnrollmentHandler?.();
    throw err;
  }
  return data as T;
}

let reauthHandler: (() => Promise<boolean>) | null = null;
/** The re-authentication dialog registers this; resolves true when the password was confirmed. */
export function setReauthHandler(fn: (() => Promise<boolean>) | null) {
  reauthHandler = fn;
}

/** Step-up for requests outside `api` (e.g. raw zip uploads): false when nobody can ask. */
export function askReauth(): Promise<boolean> {
  return reauthHandler ? reauthHandler() : Promise.resolve(false);
}

let mfaEnrollmentHandler: (() => void) | null = null;
export function setMfaEnrollmentHandler(fn: (() => void) | null) {
  mfaEnrollmentHandler = fn;
}

let unauthenticatedHandler: ((e: ApiError) => void) | null = null;
function onUnauthenticated(e: ApiError) {
  unauthenticatedHandler?.(e);
}
/** AuthContext registers this so any expired session sends the user back to sign-in. */
export function setUnauthenticatedHandler(fn: ((e: ApiError) => void) | null) {
  unauthenticatedHandler = fn;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: Json) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: Json) => request<T>("PATCH", path, body),
  put: <T>(path: string, body: Json) => request<T>("PUT", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};

export function qs(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}
